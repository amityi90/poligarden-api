#!/usr/bin/env python3
"""
PolyGarden — Supabase Database Setup & Seed Script
Companion / antagonist pairs derived from the IDEP Foundation
"A Companion Planting Chart" (based on Perennial Products NSW).

Same plants list as seed.py — only the relationship pairs differ:
they now reflect the chart exactly. A few chart entries have no
matching plant in the DB and are dropped (Apricot, Rue, Tansy,
Grass, Horseradish). A few are mapped to the closest plant:
    Marjoram        -> Oregano  (45)
    Pennyroyal      -> Mint     (31)
    Silverbeet      -> Swiss Chard (19)
    Stinging Nettle -> Nettle   (41)
    Roses           -> Rugosa Rose (120)
    Apple           -> Dwarf Apple (61)
    Cherry          -> Dwarf Cherry (64)
    Beans (any)     -> Pole Beans (11)
    Fruit Trees     -> Dwarf Apple/Pear/Plum (61/62/63)
    Squash          -> Pumpkin  (10)

Usage:
    pip install psycopg2-binary
    python db/plants_seed.py
"""

import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host":     "db.jfqtyxrbqolzbvglqnno.supabase.co",
    "port":     5432,
    "dbname":   "postgres",
    "user":     "postgres",
    "password": "eL4nGIb2scjQ6TzL",
}


def create_tables(cur):
    cur.execute("DROP TABLE IF EXISTS antagonistic_plants CASCADE;")
    cur.execute("DROP TABLE IF EXISTS companion_plants CASCADE;")
    cur.execute("DROP TABLE IF EXISTS plants CASCADE;")

    cur.execute("""
        CREATE TABLE plants (
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
            body_water       BOOL
        );
    """)

    cur.execute("""
        CREATE TABLE companion_plants (
            id                  SERIAL  PRIMARY KEY,
            plant_id            INT8    NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
            companion_plant_id  INT8    NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
            UNIQUE (plant_id, companion_plant_id)
        );
    """)

    cur.execute("""
        CREATE TABLE antagonistic_plants (
            id                      SERIAL  PRIMARY KEY,
            plant_id                INT8    NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
            antagonistic_plant_id   INT8    NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
            UNIQUE (plant_id, antagonistic_plant_id)
        );
    """)


def seed_plants(cur):
    plants = [
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

    execute_values(cur, """
        INSERT INTO plants
            (id, name, planting_start, planting_end, harvesting_start, harvesting_end,
             water, shadow, height, spread, body_water)
        VALUES %s
    """, plants)


def make_bidirectional(raw_pairs):
    seen = set()
    result = []
    for a, b in raw_pairs:
        if a == b:
            continue
        for pair in [(a, b), (b, a)]:
            if pair not in seen:
                seen.add(pair)
                result.append(pair)
    return result


def seed_companions(cur):
    """
    Companion pairs transcribed from the IDEP companion planting chart.
    IDs above the table key: see the mapping comment at the top of the file.
    """
    raw_pairs = [
        # Dwarf Apple (61)
        (61, 46),   # Apple - Chives
        (61,  5),   # Apple - Garlic
        (61, 35),   # Apple - Lavender
        (61, 44),   # Apple - Lemon Balm
        (61,  6),   # Apple - Marigold
        (61, 87),   # Apple - Mustard
        (61, 38),   # Apple - Nasturtium
        (61, 56),   # Apple - Raspberry
        (61, 17),   # Apple - Spinach
        (61, 15),   # Apple - Sunflower
        (61, 33),   # Apple - Thyme
        (61, 42),   # Apple - Yarrow

        # Asparagus (52)
        (52,  2),   # Asparagus - Basil
        (52, 28),   # Asparagus - Parsley
        (52,  1),   # Asparagus - Tomato

        # Basil (2)
        (2,   1),   # Basil - Tomato

        # Pole Beans (11) — chart's "Beans / Broad / Bush / Climbing"
        (11, 24),   # Beans - Broccoli
        (11, 26),   # Beans - Brussels Sprouts
        (11, 23),   # Beans - Cabbage
        (11,  3),   # Beans - Carrot
        (11, 25),   # Beans - Cauliflower
        (11, 88),   # Beans - Coriander
        (11, 29),   # Beans - Dill
        (11, 14),   # Beans - Corn
        (11,  8),   # Beans - Cucumber
        (11, 67),   # Beans - Eggplant
        (11, 16),   # Beans - Lettuce
        (11,  6),   # Beans - Marigold
        (11, 45),   # Beans - Marjoram (Oregano)
        (11, 28),   # Beans - Parsley
        (11, 13),   # Beans - Peas
        (11, 31),   # Beans - Pennyroyal (Mint)
        (11, 49),   # Beans - Potato
        (11, 21),   # Beans - Radish
        (11, 32),   # Beans - Rosemary
        (11, 92),   # Beans - Savory
        (11, 17),   # Beans - Spinach
        (11, 55),   # Beans - Strawberry

        # Bush Beans (12) — same companions plus Beet
        (12, 20),   # Bush Beans - Beet
        (12, 23),   # Bush Beans - Cabbage
        (12,  3),   # Bush Beans - Carrot
        (12, 25),   # Bush Beans - Cauliflower
        (12, 14),   # Bush Beans - Corn
        (12,  8),   # Bush Beans - Cucumber
        (12, 16),   # Bush Beans - Lettuce
        (12, 55),   # Bush Beans - Strawberry

        # Beet (20)
        (20, 23),   # Beet - Cabbage
        (20, 25),   # Beet - Cauliflower
        (20,  4),   # Beet - Onion
        (20, 19),   # Beet - Silverbeet (Swiss Chard)
        (20, 42),   # Beet - Yarrow

        # Borage (37)
        (37, 23),   # Borage - Cabbage
        (37, 10),   # Borage - Squash (Pumpkin)
        (37, 55),   # Borage - Strawberry
        (37,  1),   # Borage - Tomato
        (37, 42),   # Borage - Yarrow
        (37,  9),   # Borage - Zucchini

        # Cabbage (23)
        (23, 36),   # Cabbage - Chamomile
        (23, 27),   # Cabbage - Celery
        (23, 100),  # Cabbage - Chervil
        (23, 88),   # Cabbage - Coriander
        (23, 29),   # Cabbage - Dill
        (23,  5),   # Cabbage - Garlic
        (23,  6),   # Cabbage - Marigold
        (23, 105),  # Cabbage - Mulberry
        (23, 38),   # Cabbage - Nasturtium
        (23,  4),   # Cabbage - Onion
        (23, 31),   # Cabbage - Pennyroyal (Mint)
        (23, 49),   # Cabbage - Potato
        (23, 32),   # Cabbage - Rosemary
        (23, 34),   # Cabbage - Sage
        (23, 33),   # Cabbage - Thyme
        (23, 42),   # Cabbage - Yarrow

        # Carrot (3)
        (3, 46),    # Carrot - Chives
        (3, 88),    # Carrot - Coriander
        (3, 29),    # Carrot - Dill
        (3, 47),    # Carrot - Leek
        (3, 16),    # Carrot - Lettuce
        (3,  4),    # Carrot - Onion
        (3, 13),    # Carrot - Peas
        (3, 32),    # Carrot - Rosemary
        (3, 34),    # Carrot - Sage
        (3,  1),    # Carrot - Tomato

        # Celery (27)
        (27, 47),   # Celery - Leek
        (27,  1),   # Celery - Tomato

        # Dwarf Cherry (64)
        (64,  5),   # Cherry - Garlic

        # Chervil (100)
        (100, 21),  # Chervil - Radish

        # Chives (46)
        (46, 66),   # Chives - Grape
        (46, 120),  # Chives - Roses
        (46,  1),   # Chives - Tomato

        # Coriander (88) / Dill (29)
        (88,  8),   # Coriander - Cucumber
        (88,  1),   # Coriander - Tomato
        (29,  8),   # Dill - Cucumber
        (29,  1),   # Dill - Tomato

        # Corn (14)
        (14,  8),   # Corn - Cucumber
        (14, 45),   # Corn - Marjoram (Oregano)
        (14, 13),   # Corn - Peas
        (14, 49),   # Corn - Potato
        (14, 10),   # Corn - Pumpkin / Squash
        (14, 15),   # Corn - Sunflower
        (14,  9),   # Corn - Zucchini

        # Cucumber (8)
        (8, 16),    # Cucumber - Lettuce
        (8, 38),    # Cucumber - Nasturtium
        (8, 13),    # Cucumber - Peas
        (8, 21),    # Cucumber - Radish
        (8, 15),    # Cucumber - Sunflower

        # Fruit Trees -> Dwarf Apple/Pear/Plum (61/62/63)
        (62, 46),   # Fruit Trees - Chives
        (62,  5),   # Fruit Trees - Garlic
        (62,  6),   # Fruit Trees - Marigold
        (62, 87),   # Fruit Trees - Mustard
        (62, 38),   # Fruit Trees - Nasturtium
        (62, 32),   # Fruit Trees - Rosemary
        (62, 34),   # Fruit Trees - Sage
        (62, 41),   # Fruit Trees - Stinging Nettle
        (62, 42),   # Fruit Trees - Yarrow
        (63, 46),
        (63,  5),
        (63,  6),
        (63, 87),
        (63, 38),
        (63, 32),
        (63, 34),
        (63, 41),
        (63, 42),

        # Garlic (5)
        (5, 64),    # Garlic - Cherry
        (5, 120),   # Garlic - Roses
        (5,  1),    # Garlic - Tomato

        # Gooseberry (59)
        (59,  1),   # Gooseberry - Tomato

        # Lavender (35)
        (35,  3),   # Lavender - Carrot
        (35, 120),  # Lavender - Roses

        # Lemon Balm (44)
        (44,  1),   # Lemon Balm - Tomato

        # Lettuce (16)
        (16, 88),   # Lettuce - Coriander
        (16, 29),   # Lettuce - Dill
        (16,  4),   # Lettuce - Onion
        (16, 13),   # Lettuce - Peas
        (16, 21),   # Lettuce - Radish
        (16, 55),   # Lettuce - Strawberry

        # Marigold (6)
        (6, 24),    # Marigold - Broccoli
        (6, 26),    # Marigold - Brussels Sprouts
        (6,  8),    # Marigold - Cucumber
        (6, 49),    # Marigold - Potato
        (6, 120),   # Marigold - Roses
        (6, 55),    # Marigold - Strawberry
        (6,  1),    # Marigold - Tomato

        # Marjoram -> Oregano (45)
        (45, 23),   # Marjoram - Cabbage
        (45,  1),   # Marjoram - Tomato
        (45,  9),   # Marjoram - Zucchini

        # Mints (31)
        (31, 23),   # Mint - Cabbage
        (31,  1),   # Mint - Tomato

        # Nasturtium (38)
        (38, 21),   # Nasturtium - Radish
        (38, 120),  # Nasturtium - Roses
        (38,  1),   # Nasturtium - Tomato
        (38,  9),   # Nasturtium - Zucchini

        # Onion (4)
        (4, 36),    # Onion - Chamomile
        (4, 120),   # Onion - Roses
        (4, 19),    # Onion - Silverbeet
        (4, 55),    # Onion - Strawberry
        (4,  1),    # Onion - Tomato

        # Parsley (28)
        (28, 120),  # Parsley - Roses
        (28,  1),   # Parsley - Tomato

        # Parsnip (76)
        (76, 14),   # Parsnip - Corn
        (76, 13),   # Parsnip - Peas
        (76, 21),   # Parsnip - Radish

        # Potato (49)
        (49, 13),   # Potato - Peas

        # Radish (21)
        (21, 13),   # Radish - Peas

        # Raspberry (56)
        (56, 23),   # Raspberry - Cabbage

        # Rosemary (32)
        (32, 34),   # Rosemary - Sage

        # Roses (120)
        # all pair partners already covered above

        # Sage (34)
        (34, 55),   # Sage - Strawberry

        # Silverbeet (19)
        (19, 23),   # Silverbeet - Cabbage

        # Spinach (17)
        (17, 55),   # Spinach - Strawberry

        # Strawberry (55)
        # covered above

        # Tomato (1)
        # already covered via partners above

        # Yarrow (42)
        (42, 55),   # Yarrow - Strawberry
    ]

    execute_values(cur, """
        INSERT INTO companion_plants (plant_id, companion_plant_id)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, make_bidirectional(raw_pairs))


def seed_antagonists(cur):
    """
    Antagonistic pairs transcribed from the IDEP companion planting chart.
    """
    raw_pairs = [
        # Beans (Pole / Bush) — chart shows X with Chives, Fennel, Garlic, Onion, Shallot
        (11, 46),   # Beans X Chives
        (11, 30),   # Beans X Fennel
        (11,  5),   # Beans X Garlic
        (11,  4),   # Beans X Onion
        (11, 48),   # Beans X Shallot
        (11, 20),   # Climbing Beans X Beet
        (12, 46),   # Bush Beans X Chives
        (12, 30),   # Bush Beans X Fennel
        (12,  5),   # Bush Beans X Garlic
        (12,  4),   # Bush Beans X Onion
        (12, 48),   # Bush Beans X Shallot

        # Cabbage (23)
        (23, 55),   # Cabbage X Strawberry
        (23,  1),   # Cabbage X Tomato

        # Chives (46)
        (46, 13),   # Chives X Peas

        # Cucumber (8)
        (8, 49),    # Cucumber X Potato
        (8, 34),    # Cucumber X Sage

        # Fennel (30)
        (30, 88),   # Fennel X Coriander
        (30,  1),   # Fennel X Tomato

        # Garlic (5)
        (5, 13),    # Garlic X Peas

        # Onion (4)
        (4, 13),    # Onion X Peas

        # Peas (13)
        (13, 48),   # Peas X Shallot

        # Potato (49)
        (49, 61),   # Potato X Apple
        (49, 15),   # Potato X Sunflower
        (49,  1),   # Potato X Tomato

        # Rosemary (32)
        (32,  1),   # Rosemary X Tomato
    ]

    execute_values(cur, """
        INSERT INTO antagonistic_plants (plant_id, antagonistic_plant_id)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, make_bidirectional(raw_pairs))


def main():
    print("Connecting to Supabase...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Creating tables...")
        create_tables(cur)

        print("Seeding plants...")
        seed_plants(cur)

        print("Seeding companion relationships (from chart)...")
        seed_companions(cur)

        print("Seeding antagonistic relationships (from chart)...")
        seed_antagonists(cur)

        conn.commit()
        print("\nDone! Summary:")

        cur.execute("SELECT COUNT(*) FROM plants;")
        print(f"  Plants inserted       : {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM companion_plants;")
        print(f"  Companion pairs       : {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM antagonistic_plants;")
        print(f"  Antagonistic pairs    : {cur.fetchone()[0]}")

    except Exception as e:
        conn.rollback()
        print(f"\nError — rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
