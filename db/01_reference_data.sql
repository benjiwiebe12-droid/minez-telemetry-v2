-- LaVallee Mine — reference data
-- Underground gold mine, Abitibi-Témiscamingue, Quebec, Canada

CREATE TABLE zones (
    zone_id     TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

INSERT INTO zones VALUES
    ('Z-1', 'Main Drift Level 300'),
    ('Z-2', 'East Stope Level 300'),
    ('Z-3', 'Crusher Bay'),
    ('Z-4', 'Haulage Ramp'),
    ('Z-5', 'West Stope Level 250'),
    ('Z-6', 'Ventilation Station');

-- All devices that may appear as source_id
CREATE TABLE equipment (
    source_id   TEXT PRIMARY KEY,
    device_type TEXT NOT NULL,  -- 'truck', 'aq_monitor', 'wearable'
    model       TEXT,
    zone_id     TEXT REFERENCES zones(zone_id)
);

-- Underground haul trucks
INSERT INTO equipment VALUES
    ('TRK-01', 'truck',      'Sandvik TH550',  'Z-1'),
    ('TRK-02', 'truck',      'Sandvik TH550',  'Z-2'),
    ('TRK-03', 'truck',      'Sandvik TH550',  'Z-3'),
    ('TRK-04', 'truck',      'Sandvik TH550',  'Z-4'),
    ('TRK-05', 'truck',      'Sandvik TH550',  'Z-5'),
    ('TRK-06', 'truck',      'Sandvik TH550',  'Z-6'),
    ('TRK-07', 'truck',      'Caterpillar AD45', 'Z-1'),
    ('TRK-08', 'truck',      'Caterpillar AD45', 'Z-2');

-- Fixed-mount gas monitors (one per zone)
INSERT INTO equipment VALUES
    ('AQ-01',  'aq_monitor', 'RKI Eagle 2',    'Z-1'),
    ('AQ-02',  'aq_monitor', 'RKI Eagle 2',    'Z-2'),
    ('AQ-03',  'aq_monitor', 'RKI Eagle 2',    'Z-3'),
    ('AQ-04',  'aq_monitor', 'BW MicroClip',   'Z-4'),  -- older firmware
    ('AQ-05',  'aq_monitor', 'BW MicroClip',   'Z-5'),  -- older firmware
    ('AQ-06',  'aq_monitor', 'RKI Eagle 2',    'Z-6');

-- Worker wearable devices (Blackline G7c safety monitors)
INSERT INTO equipment VALUES
    ('W-001',  'wearable',   'Blackline G7c',  'Z-1'),
    ('W-002',  'wearable',   'Blackline G7c',  'Z-1'),
    ('W-003',  'wearable',   'Blackline G7c',  'Z-2'),
    ('W-004',  'wearable',   'Blackline G7c',  'Z-2'),
    ('W-005',  'wearable',   'Blackline G7c',  'Z-3'),
    ('W-006',  'wearable',   'Blackline G7c',  'Z-3'),
    ('W-007',  'wearable',   'Blackline G7c',  'Z-4'),
    ('W-008',  'wearable',   'Blackline G7c',  'Z-5'),
    ('W-009',  'wearable',   'Blackline G7c',  'Z-5'),
    ('W-010',  'wearable',   'Blackline G7c',  'Z-6');

-- Worker roster (names for the safety reports)
CREATE TABLE workers (
    worker_id   TEXT PRIMARY KEY REFERENCES equipment(source_id),
    full_name   TEXT NOT NULL
);

INSERT INTO workers VALUES
    ('W-001', 'Pierre Tremblay'),
    ('W-002', 'Marie-Claire Bouchard'),
    ('W-003', 'Jean-François Côté'),
    ('W-004', 'Kevin O''Brien'),
    ('W-005', 'Sylvie Gagnon'),
    ('W-006', 'Marco Arsenault'),
    ('W-007', 'Linda Ouellet'),
    ('W-008', 'Denis Lavoie'),
    ('W-009', 'Ahmed Belkacem'),
    ('W-010', 'Nathalie Fortin');

-- Shifts for the challenge day
CREATE TABLE shifts (
    shift_id    TEXT PRIMARY KEY,
    shift_start TIMESTAMPTZ NOT NULL,
    shift_end   TIMESTAMPTZ NOT NULL
);

INSERT INTO shifts VALUES
    ('2026-11-16-D', '2026-11-16 06:00:00+00', '2026-11-16 18:00:00+00'),
    ('2026-11-16-N', '2026-11-16 18:00:00+00', '2026-11-17 06:00:00+00');
