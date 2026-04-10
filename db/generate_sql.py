#!/usr/bin/env python3
"""
Generates db/setup.sql from the plant data in seed.py.
Run:  python db/generate_sql.py
Then paste the output SQL into Supabase Dashboard → SQL Editor → New Query.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# ── reuse the data lists from seed.py without importing psycopg2 ──────────────

PLANTS = [
    # (id, name, planting_start, planting_end, harvesting_start, harvesting_end,
    #  water ml/day, shadow, height cm, spread cm, body_water)
    (1,   "Tomato",               3,  5,  6, 10,  800, False, 150,  60, False),
    (2,   "Basil",                4,  6,  6,  9,  400, False,  60,  30, False),
    (3,   "Carrot",               2,  4,  5,  8,  300, False,  30,  10, False),
    (4,   "Onion",                9, 11,  5,  7,  250, False,  50,  15, False),
    (5,   "Garlic",              10, 12,  5,  7,  200, False,  60,  10, False),
    (6,   "Marigold",             3,  5,  6, 10,  200, False,  50,  30, False),
    (7,   "Bell Pepper",          3,  5,  7, 10,  600, False,  80,  50, False),
    (8,   "Cucumber",             4,  6,  6,  9,  700, False, 200, 100, False),
    (9,   "Zucchini",             4,  6,  6,  9,  800, False,  60, 100, False),
    (10,  "Pumpkin",              4,  5,  8, 10,  800, False,  50, 200, False),
    (11,  "Pole Beans",           4,  6,  7, 10,  400, False, 200,  30, False),
    (12,  "Bush Beans",           4,  6,  7, 10,  350, False,  50,  30, False),
    (13,  "Peas",                 1,  3,  4,  6,  300,  True, 150,  20, False),
    (14,  "Corn",                 4,  5,  7,  9,  600, False, 250,  40, False),
    (15,  "Sunflower",            4,  5,  8, 10,  400, False, 300,  60, False),
    (16,  "Lettuce",              2,  4,  4,  6,  300,  True,  30,  30, False),
    (17,  "Spinach",              2,  4,  4,  6,  300,  True,  30,  30, False),
    (18,  "Kale",                 2,  4,  5, 11,  350,  True,  80,  50, False),
    (19,  "Swiss Chard",          3,  5,  5, 11,  350,  True,  60,  40, False),
    (20,  "Beet",                 3,  5,  6,  9,  300, False,  40,  20, False),
    (21,  "Radish",               3,  5,  4,  6,  200, False,  30,  10, False),
    (22,  "Turnip",               3,  5,  5,  7,  250, False,  30,  20, False),
    (23,  "Cabbage",              2,  4,  5,  8,  400, False,  50,  50, False),
    (24,  "Broccoli",             2,  4,  4,  7,  400, False,  70,  60, False),
    (25,  "Cauliflower",          2,  4,  4,  7,  400, False,  60,  60, False),
    (26,  "Brussels Sprouts",     3,  5,  9, 12,  400, False, 100,  60, False),
    (27,  "Celery",               3,  5,  7, 10,  600,  True,  60,  30, False),
    (28,  "Parsley",              3,  5,  6, 10,  300,  True,  40,  30, False),
    (29,  "Dill",                 4,  6,  6,  9,  250, False, 100,  30, False),
    (30,  "Fennel",               4,  6,  8, 11,  300, False, 150,  50, False),
    (31,  "Mint",                 4,  6,  6, 10,  500,  True,  60,  60, False),
    (32,  "Rosemary",             3,  5,  6, 10,  200, False, 150, 100, False),
    (33,  "Thyme",                3,  5,  6, 10,  150, False,  30,  40, False),
    (34,  "Sage",                 3,  5,  6, 10,  200, False,  80,  60, False),
    (35,  "Lavender",             3,  5,  6,  8,  150, False,  80,  80, False),
    (36,  "Chamomile",            3,  5,  5,  8,  200, False,  60,  30, False),
    (37,  "Borage",               4,  6,  6, 10,  300, False,  80,  60, False),
    (38,  "Nasturtium",           4,  6,  6, 10,  200, False,  30,  50, False),
    (39,  "Calendula",            3,  5,  5, 10,  200, False,  60,  40, False),
    (40,  "Comfrey",              3,  5,  5, 11,  400,  True, 100,  80, False),
    (41,  "Nettle",               3,  5,  5, 10,  400,  True, 150,  60, False),
    (42,  "Yarrow",               4,  6,  6, 10,  150, False,  80,  60, False),
    (43,  "Echinacea",            4,  5,  7,  9,  200, False, 100,  60, False),
    (44,  "Lemon Balm",           4,  6,  6, 10,  300,  True,  80,  60, False),
    (45,  "Oregano",              4,  6,  6, 10,  200, False,  50,  40, False),
    (46,  "Chives",               3,  5,  5, 10,  250, False,  40,  20, False),
    (47,  "Leek",                 9, 11,  3,  6,  300, False,  60,  15, False),
    (48,  "Shallot",             10, 12,  5,  7,  200, False,  40,  15, False),
    (49,  "Potato",               3,  4,  6,  9,  500, False,  80,  60, False),
    (50,  "Sweet Potato",         5,  6,  8, 11,  500, False,  30, 200, False),
    (51,  "Jerusalem Artichoke",  3,  5, 10, 12,  300, False, 300,  60, False),
    (52,  "Asparagus",            3,  4,  4,  6,  400, False, 150,  60, False),
    (53,  "Globe Artichoke",     10, 12,  4,  7,  500, False, 150, 100, False),
    (54,  "Rhubarb",              3,  4,  5,  7,  400,  True, 100, 100, False),
    (55,  "Strawberry",           3,  5,  5,  7,  400, False,  20,  40, False),
    (56,  "Raspberry",           10, 12,  6,  9,  400, False, 200,  60, False),
    (57,  "Blueberry",           10, 12,  6,  8,  400, False, 150, 100, False),
    (58,  "Elderberry",          10, 12,  7,  9,  300, False, 400, 250, False),
    (59,  "Gooseberry",          10, 12,  6,  8,  300, False, 150, 120, False),
    (60,  "Black Currant",       10, 12,  6,  8,  300,  True, 150, 150, False),
    (61,  "Dwarf Apple",         10, 12,  8, 11,  400, False, 300, 200, False),
    (62,  "Dwarf Pear",          10, 12,  8, 11,  400, False, 300, 200, False),
    (63,  "Dwarf Plum",          10, 12,  7,  9,  350, False, 250, 200, False),
    (64,  "Dwarf Cherry",        10, 12,  6,  7,  350, False, 300, 200, False),
    (65,  "Fig",                 10, 12,  8, 10,  300, False, 400, 300, False),
    (66,  "Grape",               10, 12,  8, 11,  400, False, 300, 200, False),
    (67,  "Eggplant",             4,  5,  7, 10,  600, False,  80,  70, False),
    (68,  "Okra",                 4,  6,  7, 10,  500, False, 150,  60, False),
    (69,  "Melon",                4,  6,  7, 10,  700, False,  40, 200, False),
    (70,  "Watermelon",           4,  6,  7,  9,  800, False,  40, 300, False),
    (71,  "Arugula",              3,  5,  4,  6,  200,  True,  30,  20, False),
    (72,  "Endive",               3,  5,  5,  7,  250,  True,  40,  30, False),
    (73,  "Chicory",              3,  5,  6,  9,  300, False,  80,  40, False),
    (74,  "Pak Choi",             3,  5,  4,  7,  300,  True,  30,  25, False),
    (75,  "Kohlrabi",             3,  5,  5,  8,  300, False,  40,  30, False),
    (76,  "Parsnip",              3,  4,  8, 11,  300, False, 100,  20, False),
    (77,  "Celeriac",             3,  5,  9, 11,  500, False,  60,  40, False),
    (78,  "Amaranth",             4,  6,  7, 10,  300, False, 150,  60, False),
    (79,  "Quinoa",               4,  5,  8, 10,  250, False, 150,  40, False),
    (80,  "Flax",                 3,  5,  7,  8,  200, False, 100,  20, False),
    (81,  "Buckwheat",            5,  7,  7,  9,  250, False,  80,  30, False),
    (82,  "Red Clover",           3,  5,  6, 10,  250, False,  50,  40, False),
    (83,  "White Clover",         3,  5,  5, 10,  200, False,  20,  30, False),
    (84,  "Alfalfa",              3,  5,  6, 10,  300, False,  80,  40, False),
    (85,  "Hairy Vetch",          9, 11,  4,  6,  200, False, 100,  40, False),
    (86,  "Phacelia",             3,  5,  5,  7,  200, False,  60,  30, False),
    (87,  "Mustard",              3,  5,  5,  7,  200, False,  80,  40, False),
    (88,  "Coriander",            3,  5,  5,  8,  200, False,  50,  30, False),
    (89,  "Fenugreek",            4,  6,  7,  9,  250, False,  60,  30, False),
    (90,  "Cumin",                4,  6,  7,  9,  200, False,  50,  20, False),
    (91,  "Tarragon",             4,  5,  6,  9,  200, False,  80,  50, False),
    (92,  "Winter Savory",        3,  5,  6, 10,  150, False,  40,  40, False),
    (93,  "Lemon Verbena",        5,  6,  7, 10,  300, False, 150, 100, False),
    (94,  "Stevia",               5,  6,  7, 10,  300, False,  60,  40, False),
    (95,  "Radicchio",            3,  5,  5,  8,  300, False,  30,  30, False),
    (96,  "Lovage",               3,  5,  6, 10,  400,  True, 200,  80, False),
    (97,  "Valerian",             4,  5,  6,  9,  300,  True, 150,  60, False),
    (98,  "Evening Primrose",     4,  6,  7, 10,  200, False, 100,  50, False),
    (99,  "Lemongrass",           5,  6,  8, 11,  400, False, 120,  80, False),
    (100, "Chervil",              3,  5,  5,  8,  200,  True,  40,  30, False),
    # Trees
    (101, "Olive Tree",           10, 12,  9, 11,  300, False, 600, 500, False),
    (102, "Walnut",               10, 12,  9, 11,  500, False,2000,1500, False),
    (103, "Hazelnut",             10, 12,  8, 10,  300, False, 400, 300, False),
    (104, "Almond",               10, 12,  7,  9,  250, False, 600, 500, False),
    (105, "Mulberry",             10, 12,  5,  7,  400, False,1000, 800, False),
    (106, "Lemon Tree",           10, 12, 11,  3,  400, False, 400, 300, False),
    (107, "Orange Tree",          10, 12, 11,  3,  400, False, 500, 400, False),
    (108, "Pomegranate",          10, 12,  9, 11,  300, False, 500, 400, False),
    (109, "Quince",               10, 12,  9, 11,  350, False, 500, 400, False),
    (110, "Black Locust",         10, 12,  5,  6,  200, False,2000,1000, False),
    (111, "Alder",                10, 12,  1, 12,  500,  True,1500, 800, False),
    (112, "Hawthorn",             10, 12,  9, 11,  250, False, 500, 400, False),
    (113, "Medlar",               10, 12, 10, 12,  300, False, 400, 300, False),
    (114, "Serviceberry",         10, 12,  6,  7,  300, False, 500, 400, False),
    (115, "Pawpaw",               10, 12,  8, 10,  400,  True, 600, 400, False),
    (116, "Bay Laurel",           10, 12,  1, 12,  300,  True, 500, 300, False),
    # Bushes
    (117, "Blackberry",           10, 12,  6,  9,  400,  True, 200, 200, False),
    (118, "Aronia",               10, 12,  8, 10,  300,  True, 200, 150, False),
    (119, "Goji Berry",           10, 12,  7, 10,  250, False, 200, 150, False),
    (120, "Rugosa Rose",          10, 12,  8, 10,  250, False, 200, 150, False),
    (121, "Sea Buckthorn",        10, 12,  8, 10,  200, False, 400, 300, False),
    (122, "Siberian Pea Shrub",   10, 12,  6,  7,  200, False, 300, 200, False),
    (123, "Autumn Olive",         10, 12,  9, 10,  200, False, 400, 300, False),
    (124, "Jostaberry",           10, 12,  6,  8,  300, False, 150, 150, False),
    (125, "Buffaloberry",         10, 12,  7,  9,  200, False, 300, 200, False),
]

COMPANION_RAW = [
    (1,2),(1,6),(1,3),(1,28),(1,5),(1,46),(1,52),(1,37),(1,39),
    (2,7),(2,45),(2,52),
    (3,4),(3,32),(3,34),(3,16),(3,46),(3,13),(3,88),(3,100),
    (4,20),(4,36),(4,23),(4,24),
    (5,32),(5,36),(5,55),
    (6,7),(6,67),(6,8),
    (10,14),(10,11),(10,37),(11,14),(11,3),(11,32),(11,38),(9,37),(9,38),(9,11),(14,9),
    (8,11),(8,29),(8,21),(8,15),(8,38),
    (12,3),(12,8),(12,27),(12,32),
    (13,3),(13,31),(13,21),(13,17),(13,39),
    (16,21),(16,46),(16,55),(16,29),(17,55),(17,20),(18,20),(18,27),(18,38),(19,4),(19,21),
    (23,29),(23,27),(23,36),(23,38),(24,27),(24,36),(25,27),(26,33),
    (20,4),(20,16),(20,23),(20,88),(21,38),(21,100),
    (27,47),(28,52),(29,23),(29,16),
    (32,55),(33,23),(34,3),(35,1),(35,55),(36,23),(36,4),
    (37,55),(37,69),(38,23),(39,13),
    (40,1),(40,49),(40,52),(40,55),(42,1),(42,8),(46,55),(52,28),(52,2),
    (55,37),(55,16),(55,17),(55,46),
    (66,82),(66,83),(67,6),(69,37),(69,38),(70,38),
    (82,1),(83,1),(84,1),(85,11),(86,1),(86,8),(87,23),(88,3),
    (92,11),(92,12),(96,1),(97,1),(100,3),(100,21),
    # Trees
    (101,32),(101,35),(101,33),(101,82),
    (103,82),(103,83),(103,40),
    (104,35),(104,86),
    (105,82),(105,40),
    (106,2),(106,38),(107,2),(107,38),
    (108,2),(108,6),
    (110,66),(110,55),(111,56),(111,60),
    (112,56),(112,58),(114,82),(114,40),(116,1),(116,49),(116,23),
    # Bushes
    (117,40),(117,82),(118,83),(118,40),(119,35),(119,82),
    (120,5),(120,35),(120,46),(121,55),(121,82),
    (122,56),(122,57),(123,55),(123,56),(124,40),(124,83),(125,55),(125,82),
]

ANTAGONIST_RAW = [
    (30,1),(30,3),(30,8),(30,7),(30,11),(30,12),(30,16),(30,88),
    (1,23),(1,14),(1,49),
    (4,11),(4,12),(4,13),(5,11),(5,12),(5,13),(47,11),(47,13),(48,11),(48,13),
    (23,55),(23,1),
    (49,8),(49,15),(15,3),
    (20,11),(20,12),(29,3),(52,4),(52,5),
    (31,3),(31,28),(51,1),(51,15),(22,11),(67,13),(87,11),
    # Trees
    (102,1),(102,55),(102,49),(102,61),(102,56),(102,57),(102,117),(102,84),
    (110,103),(110,104),
    (30,101),(30,103),(51,103),
]


def make_bidirectional(pairs):
    seen = set()
    result = []
    for a, b in pairs:
        if a == b:
            continue
        for p in [(a, b), (b, a)]:
            if p not in seen:
                seen.add(p)
                result.append(p)
    return result


def bool_sql(v):
    return "TRUE" if v else "FALSE"


def generate():
    lines = []
    lines.append("-- PolyGarden database setup")
    lines.append("-- Generated by db/generate_sql.py")
    lines.append("-- Paste into: Supabase Dashboard → SQL Editor → New Query\n")

    # Schema
    lines.append("DROP TABLE IF EXISTS antagonistic_plants CASCADE;")
    lines.append("DROP TABLE IF EXISTS companion_plants CASCADE;")
    lines.append("DROP TABLE IF EXISTS plants CASCADE;\n")

    lines.append("""CREATE TABLE plants (
    id               INT8 PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    planting_start   INT2,
    planting_end     INT2,
    harvesting_start INT2,
    harvesting_end   INT2,
    water            INT8,
    shadow           BOOL,
    height           INT2,
    spread           INT2,
    body_water       BOOL,
    is_tree          BOOL NOT NULL DEFAULT FALSE
);\n""")

    lines.append("""CREATE TABLE companion_plants (
    id                  SERIAL PRIMARY KEY,
    plant_id            INT8 NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    companion_plant_id  INT8 NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    UNIQUE (plant_id, companion_plant_id)
);\n""")

    lines.append("""CREATE TABLE antagonistic_plants (
    id                      SERIAL PRIMARY KEY,
    plant_id                INT8 NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    antagonistic_plant_id   INT8 NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    UNIQUE (plant_id, antagonistic_plant_id)
);\n""")

    # IDs 101–116 are trees
    TREE_IDS = set(range(101, 117))

    # Plants
    lines.append("INSERT INTO plants (id, name, planting_start, planting_end, harvesting_start, harvesting_end, water, shadow, height, spread, body_water, is_tree) VALUES")
    rows = []
    for p in PLANTS:
        id_, name, ps, pe, hs, he, w, sh, h, sp, bw = p
        it = bool_sql(id_ in TREE_IDS)
        rows.append(
            f"  ({id_}, '{name}', {ps}, {pe}, {hs}, {he}, {w}, {bool_sql(sh)}, {h}, {sp}, {bool_sql(bw)}, {it})"
        )
    lines.append(",\n".join(rows) + ";\n")

    # Companions
    companions = make_bidirectional(COMPANION_RAW)
    lines.append("INSERT INTO companion_plants (plant_id, companion_plant_id) VALUES")
    rows = [f"  ({a}, {b})" for a, b in companions]
    lines.append(",\n".join(rows) + ";\n")

    # Antagonists
    antagonists = make_bidirectional(ANTAGONIST_RAW)
    lines.append("INSERT INTO antagonistic_plants (plant_id, antagonistic_plant_id) VALUES")
    rows = [f"  ({a}, {b})" for a, b in antagonists]
    lines.append(",\n".join(rows) + ";\n")

    return "\n".join(lines)


if __name__ == "__main__":
    sql = generate()
    out_path = os.path.join(os.path.dirname(__file__), "setup.sql")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sql)
    print(f"Written {len(sql):,} chars to {out_path}")
    print(f"  Plants            : {len(PLANTS)}")
    print(f"  Companion pairs   : {len(make_bidirectional(COMPANION_RAW))}")
    print(f"  Antagonist pairs  : {len(make_bidirectional(ANTAGONIST_RAW))}")
