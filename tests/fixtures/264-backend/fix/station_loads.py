"""Named structural load stations with concurrent recovery (issue #213).

Every station reports the reaction on its retained part: the force and moment the
rest of the aircraft exerts on it,

    R = -sum_i F_i,        M_ref = -sum_i [ (r_i - r_ref) x F_i + C_i ]

over all loads acting on the retained part (located aerodynamic and propulsion
forces, gravity, and d'Alembert inertia forces with intrinsic inertia couples).
This is the convention of the existing cut ("reactions act on retained material").
All stations come from one balanced recovery at one instant, so they are concurrent.

Two station kinds:
- plane: a fuselage cut at a station aft of the nose; distributed masses and body
  crossflow strips are clipped at the plane by the verified cut machinery.
- part: a set of mass components plus the aerodynamic/propulsion loads attributed
  to them (wing halves, V-tail panels, equipment mounts), cut at their attachment.

Units: in, lbf, in-lbf; body frame x forward, y right, z down.
See docs/mechanics/STATION_LOADS.md (Station 9).
"""
from __future__ import annotations

import math

import numpy as np

from .aero_strip_provider import component_of

SCHEMA = 'station-loads-v1'


def _panel_frame(cant_deg, side):
    """Unit axes for a V-tail panel: span (outboard along the panel), chord (aft), normal."""
    cant = math.radians(cant_deg)
    span = np.array([0.0, side*math.cos(cant), math.sin(cant)])
    chord = np.array([-1.0, 0.0, 0.0])
    return dict(span=span.tolist(), chord=chord.tolist(), normal=np.cross(span, chord).tolist())


def default_stations(definition):
    """Default station list (estimate; owner confirms in #213/#199).

    Fuselage planes: forward of wing, wing carry-through, aft of wing, tail attachment.
    Parts: left/right wing root, left/right V-tail root, motor/propeller, battery and
    payload/avionics mounts (only for components present in the definition).
    """
    g = definition['geometry']
    ids = {c['id'] for c in definition['components']}
    le, chord = g['wing_le_station_in'], g['wing_chord_in']
    stations = [
        dict(id='fuselage-forward-of-wing', kind='plane', station_in=le - 1.0, retain='aft',
             description='Fuselage 1 in forward of the wing leading edge; aft part retained'),
        dict(id='fuselage-wing-carry-through', kind='plane', station_in=le + chord/2, retain='aft',
             description='Fuselage at mid wing chord; aft part retained'),
        dict(id='fuselage-aft-of-wing', kind='plane', station_in=le + chord + 1.0, retain='aft',
             description='Fuselage 1 in aft of the wing trailing edge; aft part retained'),
        dict(id='fuselage-tail-attachment', kind='plane', station_in=g['tail_le_station_in'], retain='aft',
             description='Fuselage at the V-tail leading edge; aft part retained'),
    ]
    for side, name in ((-1, 'left'), (1, 'right')):
        wing = f'wing-{name}'
        if wing in ids:
            stations.append(dict(id=f'wing-root-{name}', kind='part', components=[wing], aero=[wing], propulsion=False,
                                 reference_B_in=[-(le + chord/4), side*g['wing_root_spacing_in']/2, g['wing_z_in']],
                                 description=f'{name.capitalize()} wing root at root quarter chord'))
        tail = f'tail-{name}'
        if tail in ids:
            stations.append(dict(id=f'tail-root-{name}', kind='part', components=[tail], aero=[tail], propulsion=False,
                                 reference_B_in=[-(g['tail_le_station_in'] + g['tail_chord_in']/4),
                                                 side*g['tail_root_spacing_in']/2, g['tail_root_z_in']],
                                 panel_frame=_panel_frame(g['tail_down_cant_deg'], side),
                                 description=f'{name.capitalize()} V-tail panel root at root quarter chord'))
    for component, sid, text, propulsion in (('propulsion', 'motor-mount', 'Motor and propeller mount', True),
                                             ('battery', 'battery-mount', 'Battery mount', False),
                                             ('payload', 'payload-mount', 'Payload and avionics mount', False)):
        if component in ids:
            stations.append(dict(id=sid, kind='part', components=[component], aero=[], propulsion=propulsion,
                                 reference_B_in=None, description=text + ' at the component centroid'))
    return stations


def _row_component(row):
    """Component a recovery-ledger row belongs to: mass rows by id, applied rows by element name."""
    if row['kind'] in ('weight', 'inertia'):
        return 'mass:' + (row['id'][len('inertia-'):] if row['id'].startswith('inertia-') else row['id'])
    name = row['name']
    if name in ('wing-left', 'wing-right', 'tail-left', 'tail-right', 'body'):
        return name
    if name.startswith('fixed propulsion'):
        return 'propulsion'
    for prefix, kind in (('wing ', 'wing'), ('tail ', 'tail')):
        if name.startswith(prefix):
            return component_of({'kind': kind, 'name': name})
    return 'body'


def _reaction(rows, reference):
    ref = np.asarray(reference, dtype=float)
    force, moment = np.zeros(3), np.zeros(3)
    for row in rows:
        f = np.asarray(row['force_B_lbf'], dtype=float)
        force += f
        moment += np.cross(np.asarray(row['position_B_in'], dtype=float) - ref, f) + np.asarray(row['free_couple_B_in_lbf'])
    return -force, -moment


def _available_stations(plant, stations):
    """Resultant-only data cannot resolve a plane cutting distributed components."""
    selected = default_stations(plant.inputs['definition']) if stations is None else stations
    if plant.aero_dataset.get('load_resolution') == 'component-resultant':
        if stations is not None and any(s['kind'] == 'plane' for s in stations):
            raise ValueError('component-resultant tables cannot resolve distributed plane cuts')
        return [s for s in selected if s['kind'] != 'plane']
    return selected


def recover_stations(plant, state, field, derivative, time_s=0.0, stations=None):
    """Concurrent reactions at every station for one plant evaluation."""
    stations = _available_stations(plant, stations)
    base = plant.recover(state, field, derivative, time_s)
    mass_positions = {row['id']: row['position_B_in'] for row in base['ledger'] if row['kind'] == 'weight'}
    results = []
    for station in stations:
        if station['kind'] == 'plane':
            cut = dict(station_in=station['station_in'], retain=station['retain'])
            recovered = plant.recover(state, field, derivative, time_s, cut=cut)
            force, moment = recovered['cut_force_B_lbf'], recovered['cut_moment_B_in_lbf']
            reference = recovered['cut_origin_B_in']
            balanced = recovered['balanced']
        else:
            wanted = {'mass:' + c for c in station['components']} | set(station['aero'])
            if station['propulsion']:
                wanted.add('propulsion')
            rows = [row for row in base['ledger'] if _row_component(row) in wanted]
            reference = station['reference_B_in'] or mass_positions[station['components'][0]]
            f, m = _reaction(rows, reference)
            force, moment, balanced = f.tolist(), m.tolist(), base['balanced']
        entry = dict(id=station['id'], kind=station['kind'], reference_B_in=list(reference),
                     force_B_lbf=None if force is None else list(force),
                     moment_B_in_lbf=None if moment is None else list(moment), balanced=bool(balanced))
        if station.get('panel_frame') and force is not None:
            axes = station['panel_frame']
            entry['panel_components'] = {
                'shear_normal_lbf': float(np.dot(force, axes['normal'])),
                'shear_chordwise_lbf': float(np.dot(force, axes['chord'])),
                'axial_span_lbf': float(np.dot(force, axes['span'])),
                'bending_about_chord_in_lbf': float(np.dot(moment, axes['chord'])),
                'bending_about_normal_in_lbf': float(np.dot(moment, axes['normal'])),
                'torsion_about_span_in_lbf': float(np.dot(moment, axes['span']))}
        results.append(entry)
    return dict(schema=SCHEMA, time_s=float(time_s), whole_body_balanced=bool(base['balanced']),
                whole_force_residual_lbf=base['whole_force_residual_lbf'],
                whole_moment_residual_CG_in_lbf=base['whole_moment_residual_CG_in_lbf'], stations=results,
                convention='Reaction on the retained part: force/moment the rest of the aircraft exerts on it; '
                           'moments about the station reference point; body frame x fwd, y right, z down.')


class StationModel:
    """Fast concurrent station recovery for one plant (vectorized; same physics as recover_stations).

    State-independent geometry is precomputed once: for each station, the retained mass
    pieces (mass, centroid, intrinsic inertia after exact axial clipping) and, for each
    ledger element, the retained weight and load point (body crossflow bins that straddle
    a plane are split at the plane, preserving force and first moment). Per evaluation:

        a_i   = a_cg + alpha x rho_i + omega x (omega x rho_i)          (rho_i = r_i - r_cg)
        F     = -( sum_i m_i (g_B - a_i) + sum_e w_e F_e )
        M_ref = -( sum_i [(r_i - r_ref) x m_i (g_B - a_i) - I_i alpha - omega x (I_i omega)]
                   + sum_e w_e [(p_e - r_ref) x F_e + C_e] )
    """

    def __init__(self, plant, stations=None):
        from .aircraft_workspace import G_IN_S2, _intrinsic, _position, _retained
        self.plant = plant
        definition = plant.inputs['definition']
        self.stations = _available_stations(plant, stations)
        self.cg = np.asarray(plant.mass_properties['cg_B_in'], dtype=float)
        if plant.aero_dataset.get('load_resolution') == 'component-resultant':
            # Table element geometry is fixed. Do not require an unrelated trim
            # speed to lie in coverage merely to prepare structural geometry.
            probe = dict(ledger=[dict(name=t.component, kind=t.component, position_B_in=list(t.reference_point_B_in))
                                 for t in plant._aero.provider.components] +
                                [dict(name='fixed propulsion', kind='propulsion', position_B_in=plant._aero.prop_position_B_in)])
        else:
            probe_state = plant.initial_state(0.0, 0.0)
            probe = plant.evaluate(probe_state, dict(left_tail_deg=0.0, right_tail_deg=0.0, aileron_deg=0.0,
                                                      thrust_lbf=plant.inputs['bench']['target']['trim_thrust_min_lbf']))[0]
        self.element_names = [e['name'] for e in probe['ledger']]
        components = {c['id']: c for c in plant._components}
        g = definition['geometry']
        ds = g['fuselage_length_in']/plant.inputs['field_case']['discretization']['body_strips']
        self.element_sources = [_row_component(dict(kind='applied', name=name)) for name in self.element_names]
        self.prepared = []
        for station in self.stations:
            pieces, weights, points = [], [], []
            if station['kind'] == 'plane':
                cut = dict(station_in=station['station_in'], retain=station['retain'])
                aft = cut['retain'] == 'aft'
                for c in components.values():
                    fraction, centroid = _retained(c, cut)
                    if fraction:
                        piece = dict(c, weight_lbf=c['weight_lbf']*fraction, station_in=centroid)
                        if piece['model'] != 'point':
                            piece['length_in'] = c['length_in']*fraction
                        pieces.append(piece)
                for element in probe['ledger']:
                    x = element['position_B_in']
                    station_x = -x[0]
                    if element['kind'] == 'body-crossflow' and station_x - ds/2 < cut['station_in'] < station_x + ds/2:
                        lo, hi = ((cut['station_in'], station_x + ds/2) if aft else (station_x - ds/2, cut['station_in']))
                        weights.append((hi - lo)/ds)
                        points.append([-(lo + hi)/2, x[1], x[2]])
                    else:
                        weights.append(1.0 if (station_x >= cut['station_in']) == aft else 0.0)
                        points.append(list(x))
                reference = [-cut['station_in'], 0.0, 0.0]
            else:
                pieces = [components[c] for c in station['components']]
                wanted = set(station['aero']) | ({'propulsion'} if station['propulsion'] else set())
                for element in probe['ledger']:
                    weights.append(1.0 if _row_component(dict(kind='applied', name=element['name'])) in wanted else 0.0)
                    points.append(list(element['position_B_in']))
                reference = station['reference_B_in'] or _position(components[station['components'][0]]).tolist()
            # Store piece IDs, names, and retained weight_lbf for retained masses
            piece_ids = [p['id'] for p in pieces]
            piece_names = [p['name'] for p in pieces]
            piece_weights = [p['weight_lbf'] for p in pieces]
            self.prepared.append(dict(
                id=station['id'], kind=station['kind'], reference=np.asarray(reference, dtype=float),
                masses=np.array([p['weight_lbf']/G_IN_S2 for p in pieces]),
                positions=np.array([_position(p) for p in pieces]).reshape(-1, 3),
                inertias=np.array([_intrinsic(p) for p in pieces]).reshape(-1, 3, 3),
                weights=np.asarray(weights), points=np.asarray(points, dtype=float),
                panel_frame=station.get('panel_frame'),
                piece_ids=piece_ids, piece_names=piece_names, piece_weights=piece_weights,
                element_sources=self.element_sources))

    def evaluate(self, state, field, derivative, time_s=0.0, contributions=False):
        """Concurrent reactions at every station. contributions=True adds, per station, the
        reaction split into applied (aero + propulsion), gravity and inertia (d'Alembert
        forces and intrinsic inertia couples) parts, in the same reaction convention; the
        parts sum to the total to rounding."""
        from .aircraft_transient import G_N, IN_M
        from .conventions import rotation_matrix
        if [e['name'] for e in field['ledger']] != self.element_names:
            raise ValueError('field ledger does not match the prepared station geometry')
        omega = np.asarray(state.omega_B_radps, dtype=float)
        alpha = np.asarray(derivative.omegadot_B_radps2, dtype=float)
        a_cg = (derivative.vdot_B_mps2 + np.cross(omega, state.v_CG_B_mps))/IN_M
        g_B = rotation_matrix(state.q_NB).T @ G_N/IN_M
        forces = np.array([e['force_B_lbf'] for e in field['ledger']], dtype=float)
        couples = np.array([e['free_couple_B_in_lbf'] for e in field['ledger']], dtype=float)
        results = []
        for s in self.prepared:
            ref = s['reference']
            rho = s['positions'] - self.cg
            a_i = a_cg + np.cross(alpha, rho) + np.cross(omega, np.cross(omega, rho))
            f_mass = s['masses'][:, None]*(g_B - a_i)
            c_mass = -np.einsum('kij,j->ki', s['inertias'], alpha) - np.cross(omega, np.einsum('kij,j->ki', s['inertias'], omega))
            w = s['weights'][:, None]
            f_aero = w*forces
            total_f = f_mass.sum(axis=0) + f_aero.sum(axis=0)
            total_m = (np.cross(s['positions'] - ref, f_mass).sum(axis=0) + c_mass.sum(axis=0)
                       + np.cross(s['points'] - ref, f_aero).sum(axis=0) + (w*couples).sum(axis=0))
            force, moment = -total_f, -total_m
            entry = dict(id=s['id'], kind=s['kind'], reference_B_in=ref.tolist(), force_B_lbf=force.tolist(),
                         moment_B_in_lbf=moment.tolist())
            if contributions:
                f_grav = s['masses'][:, None]*g_B
                f_inert = -s['masses'][:, None]*a_i
                arm = s['positions'] - ref
                entry['contributions'] = dict(
                    applied=dict(force_B_lbf=(-f_aero.sum(axis=0)).tolist(),
                                 moment_B_in_lbf=(-(np.cross(s['points'] - ref, f_aero).sum(axis=0)
                                                    + (w*couples).sum(axis=0))).tolist()),
                    gravity=dict(force_B_lbf=(-f_grav.sum(axis=0)).tolist(),
                                 moment_B_in_lbf=(-np.cross(arm, f_grav).sum(axis=0)).tolist()),
                    inertia=dict(force_B_lbf=(-f_inert.sum(axis=0)).tolist(),
                                 moment_B_in_lbf=(-(np.cross(arm, f_inert).sum(axis=0) + c_mass.sum(axis=0))).tolist()))
                # contributions['applied_by_source']: sum of applied loads grouped by source
                applied_by_source = {}
                sources = s['element_sources']
                for i, src in enumerate(sources):
                    if src not in applied_by_source:
                        applied_by_source[src] = dict(force_B_lbf=np.zeros(3), moment_B_in_lbf=np.zeros(3))
                    applied_by_source[src]['force_B_lbf'] += f_aero[i]
                    applied_by_source[src]['moment_B_in_lbf'] += np.cross(s['points'][i] - ref, f_aero[i]) + (w[i]*couples[i])
                # Only include sources whose retained weights are not all zero
                # Retained weights for a source = sum of weights for elements with that source
                retained_weights_by_source = {}
                for i, src in enumerate(sources):
                    if src not in retained_weights_by_source:
                        retained_weights_by_source[src] = 0.0
                    retained_weights_by_source[src] += s['weights'][i]
                # Filter out sources with zero retained weight
                applied_by_source_filtered = {src: data for src, data in applied_by_source.items()
                                               if retained_weights_by_source[src] > 0}
                # Note: applied_by_source values are the applied loads on the body (positive),
                # but contributions['applied'] uses reaction convention (negative)
                # So we apply the negative sign here to match
                entry['contributions']['applied_by_source'] = {src: dict(
                    force_B_lbf=(-data['force_B_lbf']).tolist(),
                    moment_B_in_lbf=(-data['moment_B_in_lbf']).tolist()
                ) for src, data in applied_by_source_filtered.items()}
                # contributions['retained']: masses and applied_elements
                # masses: from the station's retained pieces (store id/name/weight_lbf)
                retained_masses = []
                for i, pid in enumerate(s['piece_ids']):
                    retained_masses.append(dict(
                        id=pid,
                        name=s['piece_names'][i],
                        weight_lbf=float(s['piece_weights'][i]),
                        position_B_in=s['positions'][i].tolist()
                    ))
                # applied_elements: elements with weight > 0; force_B_lbf = weight * ledger force
                retained_applied_elements = []
                for i, src in enumerate(s['element_sources']):
                    weight = s['weights'][i]
                    if weight > 0:
                        # force_B_lbf is the applied load on the body (not reaction-signed)
                        retained_applied_elements.append(dict(
                            name=self.element_names[i],
                            source=src,
                            weight=float(weight),
                            point_B_in=s['points'][i].tolist(),
                            force_B_lbf=(weight * forces[i]).tolist()
                        ))
                entry['contributions']['retained'] = dict(
                    masses=retained_masses,
                    applied_elements=retained_applied_elements
                )
            if s['panel_frame']:
                axes = s['panel_frame']
                entry['panel_components'] = {
                    'shear_normal_lbf': float(np.dot(force, axes['normal'])),
                    'shear_chordwise_lbf': float(np.dot(force, axes['chord'])),
                    'axial_span_lbf': float(np.dot(force, axes['span'])),
                    'bending_about_chord_in_lbf': float(np.dot(moment, axes['chord'])),
                    'bending_about_normal_in_lbf': float(np.dot(moment, axes['normal'])),
                    'torsion_about_span_in_lbf': float(np.dot(moment, axes['span']))}
            results.append(entry)
        return dict(schema=SCHEMA, time_s=float(time_s), stations=results)
