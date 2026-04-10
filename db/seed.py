#!/usr/bin/env python3
"""
PolyGarden — Supabase Database Setup & Seed Script
Creates 3 tables and inserts 100 plants with companion/antagonist relationships.

Usage:
    pip install psycopg2-binary
    python db/seed.py
"""

import psycopg2
from psycopg2.extras import execute_values

# ============================================================
#  CONFIGURATION
#  Find these at: Supabase Dashboard → Settings → Database
# ============================================================
DB_CONFIG = {
    "host":     "db.jfqtyxrbqolzbvglqnno.supabase.co",
    "port":     5432,
    "dbname":   "postgres",
    "user":     "postgres",
    "password": "eL4nGIb2scjQ6TzL",
}
# ============================================================


def create_tables(cur):
    """Drop and recreate the 3 core tables."""

    # Drop in reverse dependency order
    cur.execute("DROP TABLE IF EXISTS antagonistic_plants CASCADE;")
    cur.execute("DROP TABLE IF EXISTS companion_plants CASCADE;")
    cur.execute("DROP TABLE IF EXISTS plants CASCADE;")

    cur.execute("""
        CREATE TABLE plants (
            id               INT8 PRIMARY KEY,
            name             TEXT NOT NULL UNIQUE,
            planting_start   INT2,   -- month 1–12
            planting_end     INT2,   -- month 1–12
            harvesting_start INT2,   -- month 1–12
            harvesting_end   INT2,   -- month 1–12
            water            INT8,   -- ml/day per plant
            shadow           BOOL,   -- tolerates / prefers shade
            height           INT2,   -- cm at maturity
            spread           INT2,   -- cm lateral spread
            body_water       BOOL    -- sensitive to water on leaves
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
    """
    100 plants — values based on temperate / Mediterranean climate (Northern Hemisphere).
    Columns: (id, name, planting_start, planting_end, harvesting_start, harvesting_end,
              water ml/day, shadow, height cm, spread cm, body_water)
    """
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

        # --- TREES ---
        # (id, name, planting_start, planting_end, harvesting_start, harvesting_end,
        #  water ml/day, shadow, height cm, spread cm, body_water)
        (101, "Olive Tree",           10, 12,  9, 11,  300, False, 600, 500, False),
        (102, "Walnut",               10, 12,  9, 11,  500, False,2000,1500, False),
        (103, "Hazelnut",             10, 12,  8, 10,  300, False, 400, 300, False),
        (104, "Almond",               10, 12,  7,  9,  250, False, 600, 500, False),
        (105, "Mulberry",             10, 12,  5,  7,  400, False,1000, 800, False),
        (106, "Lemon Tree",           10, 12, 11,  3,  400, False, 400, 300, False),
        (107, "Orange Tree",          10, 12, 11,  3,  400, False, 500, 400, False),
        (108, "Pomegranate",          10, 12,  9, 11,  300, False, 500, 400, False),
        (109, "Quince",               10, 12,  9, 11,  350, False, 500, 400, False),
        (110, "Black Locust",         10, 12,  5,  6,  200, False,2000,1000, False),  # nitrogen fixer
        (111, "Alder",                10, 12,  1, 12,  500,  True,1500, 800, False),  # nitrogen fixer
        (112, "Hawthorn",             10, 12,  9, 11,  250, False, 500, 400, False),
        (113, "Medlar",               10, 12, 10, 12,  300, False, 400, 300, False),
        (114, "Serviceberry",         10, 12,  6,  7,  300, False, 500, 400, False),
        (115, "Pawpaw",               10, 12,  8, 10,  400,  True, 600, 400, False),
        (116, "Bay Laurel",           10, 12,  1, 12,  300,  True, 500, 300, False),

        # --- BUSHES ---
        (117, "Blackberry",           10, 12,  6,  9,  400,  True, 200, 200, False),
        (118, "Aronia",               10, 12,  8, 10,  300,  True, 200, 150, False),
        (119, "Goji Berry",           10, 12,  7, 10,  250, False, 200, 150, False),
        (120, "Rugosa Rose",          10, 12,  8, 10,  250, False, 200, 150, False),
        (121, "Sea Buckthorn",        10, 12,  8, 10,  200, False, 400, 300, False),  # nitrogen fixer
        (122, "Siberian Pea Shrub",   10, 12,  6,  7,  200, False, 300, 200, False),  # nitrogen fixer
        (123, "Autumn Olive",         10, 12,  9, 10,  200, False, 400, 300, False),  # nitrogen fixer
        (124, "Jostaberry",           10, 12,  6,  8,  300, False, 150, 150, False),
        (125, "Buffaloberry",         10, 12,  7,  9,  200, False, 300, 200, False),  # nitrogen fixer
    ]

    execute_values(cur, """
        INSERT INTO plants
            (id, name, planting_start, planting_end, harvesting_start, harvesting_end,
             water, shadow, height, spread, body_water)
        VALUES %s
    """, plants)


def make_bidirectional(raw_pairs):
    """Given one-directional pairs, return all unique bidirectional pairs."""
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
    Classic permaculture companion pairs.
    Each pair is stored bidirectionally so queries like
    "what companions does plant X have?" work with a simple WHERE plant_id = X.
    """
    raw_pairs = [
        # Tomato guild
        (1,  2),   # Tomato ↔ Basil          (repels aphids/whitefly, improves flavour)
        (1,  6),   # Tomato ↔ Marigold        (repels nematodes)
        (1,  3),   # Tomato ↔ Carrot          (loosen soil around roots)
        (1, 28),   # Tomato ↔ Parsley         (repels asparagus beetles)
        (1,  5),   # Tomato ↔ Garlic          (repels spider mites)
        (1, 46),   # Tomato ↔ Chives          (deters aphids)
        (1, 52),   # Tomato ↔ Asparagus       (repels asparagus beetles mutually)
        (1, 37),   # Tomato ↔ Borage          (repels tomato hornworm)
        (1, 39),   # Tomato ↔ Calendula       (trap crop for aphids)
        # Basil
        (2,  7),   # Basil ↔ Bell Pepper
        (2, 45),   # Basil ↔ Oregano
        (2, 52),   # Basil ↔ Asparagus
        # Carrot
        (3,  4),   # Carrot ↔ Onion           (repel each other's flies)
        (3, 32),   # Carrot ↔ Rosemary        (repels carrot fly)
        (3, 34),   # Carrot ↔ Sage            (repels carrot fly)
        (3, 16),   # Carrot ↔ Lettuce
        (3, 46),   # Carrot ↔ Chives
        (3, 13),   # Carrot ↔ Peas
        (3, 88),   # Carrot ↔ Coriander
        (3, 100),  # Carrot ↔ Chervil         (improves growth)
        # Onion / Allium guild
        (4, 20),   # Onion ↔ Beet
        (4, 36),   # Onion ↔ Chamomile        (improves onion growth)
        (4, 23),   # Onion ↔ Cabbage
        (4, 24),   # Onion ↔ Broccoli
        # Garlic
        (5, 32),   # Garlic ↔ Rosemary
        (5, 36),   # Garlic ↔ Chamomile
        (5, 55),   # Garlic ↔ Strawberry      (repels grey mould)
        # Marigold (benefits almost everything via nematode suppression)
        (6,  7),   # Marigold ↔ Bell Pepper
        (6, 67),   # Marigold ↔ Eggplant
        (6,  8),   # Marigold ↔ Cucumber
        # Three Sisters
        (10, 14),  # Pumpkin ↔ Corn
        (10, 11),  # Pumpkin ↔ Pole Beans
        (10, 37),  # Pumpkin ↔ Borage
        (11, 14),  # Pole Beans ↔ Corn        (nitrogen fixation feeds corn)
        (11,  3),  # Pole Beans ↔ Carrot
        (11, 32),  # Pole Beans ↔ Rosemary
        (11, 38),  # Pole Beans ↔ Nasturtium
        (9,  37),  # Zucchini ↔ Borage
        (9,  38),  # Zucchini ↔ Nasturtium
        (9,  11),  # Zucchini ↔ Pole Beans
        (14,  9),  # Corn ↔ Zucchini
        # Cucumber
        (8, 11),   # Cucumber ↔ Pole Beans
        (8, 29),   # Cucumber ↔ Dill
        (8, 21),   # Cucumber ↔ Radish        (radish repels cucumber beetle)
        (8, 15),   # Cucumber ↔ Sunflower     (sunflower provides climbing support & shade)
        (8, 38),   # Cucumber ↔ Nasturtium
        # Bush beans
        (12,  3),  # Bush Beans ↔ Carrot
        (12,  8),  # Bush Beans ↔ Cucumber
        (12, 27),  # Bush Beans ↔ Celery
        (12, 32),  # Bush Beans ↔ Rosemary
        # Peas
        (13,  3),  # Peas ↔ Carrot
        (13, 31),  # Peas ↔ Mint              (repels pea moth)
        (13, 21),  # Peas ↔ Radish
        (13, 17),  # Peas ↔ Spinach
        (13, 39),  # Peas ↔ Calendula
        # Lettuce / greens
        (16, 21),  # Lettuce ↔ Radish
        (16, 46),  # Lettuce ↔ Chives
        (16, 55),  # Lettuce ↔ Strawberry
        (16, 29),  # Lettuce ↔ Dill
        (17, 55),  # Spinach ↔ Strawberry
        (17, 20),  # Spinach ↔ Beet
        (18, 20),  # Kale ↔ Beet
        (18, 27),  # Kale ↔ Celery
        (18, 38),  # Kale ↔ Nasturtium
        (19,  4),  # Swiss Chard ↔ Onion
        (19, 21),  # Swiss Chard ↔ Radish
        # Brassicas
        (23, 29),  # Cabbage ↔ Dill
        (23, 27),  # Cabbage ↔ Celery
        (23, 36),  # Cabbage ↔ Chamomile
        (23, 38),  # Cabbage ↔ Nasturtium
        (24, 27),  # Broccoli ↔ Celery
        (24, 36),  # Broccoli ↔ Chamomile
        (25, 27),  # Cauliflower ↔ Celery
        (26, 33),  # Brussels Sprouts ↔ Thyme
        # Beet
        (20,  4),  # Beet ↔ Onion
        (20, 16),  # Beet ↔ Lettuce
        (20, 23),  # Beet ↔ Cabbage
        (20, 88),  # Beet ↔ Coriander
        # Radish
        (21, 38),  # Radish ↔ Nasturtium
        (21, 100), # Radish ↔ Chervil
        # Celery / Leek
        (27, 47),  # Celery ↔ Leek
        # Parsley / Asparagus
        (28, 52),  # Parsley ↔ Asparagus
        # Dill
        (29, 23),  # Dill ↔ Cabbage
        (29, 16),  # Dill ↔ Lettuce
        # Herbs (general pollinator/pest-repellent benefit)
        (32, 55),  # Rosemary ↔ Strawberry
        (33, 23),  # Thyme ↔ Cabbage
        (34,  3),  # Sage ↔ Carrot
        (35,  1),  # Lavender ↔ Tomato
        (35, 55),  # Lavender ↔ Strawberry
        (36, 23),  # Chamomile ↔ Cabbage
        (36,  4),  # Chamomile ↔ Onion
        # Borage
        (37, 55),  # Borage ↔ Strawberry      (improves yield, repels pests)
        (37, 69),  # Borage ↔ Melon
        # Nasturtium
        (38, 23),  # Nasturtium ↔ Cabbage     (trap crop for aphids)
        # Calendula
        (39, 13),  # Calendula ↔ Peas
        # Comfrey (dynamic accumulator — benefits neighbours via mulch)
        (40,  1),  # Comfrey ↔ Tomato
        (40, 49),  # Comfrey ↔ Potato
        (40, 52),  # Comfrey ↔ Asparagus
        (40, 55),  # Comfrey ↔ Strawberry
        # Yarrow (attracts predatory insects)
        (42,  1),  # Yarrow ↔ Tomato
        (42,  8),  # Yarrow ↔ Cucumber
        # Chives
        (46, 55),  # Chives ↔ Strawberry
        # Asparagus
        (52, 28),  # Asparagus ↔ Parsley
        (52,  2),  # Asparagus ↔ Basil
        # Strawberry guild
        (55, 37),  # Strawberry ↔ Borage
        (55, 16),  # Strawberry ↔ Lettuce
        (55, 17),  # Strawberry ↔ Spinach
        (55, 46),  # Strawberry ↔ Chives
        # Grape
        (66, 82),  # Grape ↔ Red Clover
        (66, 83),  # Grape ↔ White Clover
        # Eggplant
        (67,  6),  # Eggplant ↔ Marigold
        # Melon
        (69, 37),  # Melon ↔ Borage
        (69, 38),  # Melon ↔ Nasturtium
        (70, 38),  # Watermelon ↔ Nasturtium
        # Nitrogen fixers (clover, alfalfa, vetch benefit most neighbours)
        (82,  1),  # Red Clover ↔ Tomato
        (83,  1),  # White Clover ↔ Tomato
        (84,  1),  # Alfalfa ↔ Tomato
        (85, 11),  # Hairy Vetch ↔ Pole Beans
        # Phacelia (best bee-attractor)
        (86,  1),  # Phacelia ↔ Tomato
        (86,  8),  # Phacelia ↔ Cucumber
        # Mustard (trap crop for brassica pests)
        (87, 23),  # Mustard ↔ Cabbage
        # Coriander
        (88,  3),  # Coriander ↔ Carrot
        # Winter savory
        (92, 11),  # Winter Savory ↔ Pole Beans
        (92, 12),  # Winter Savory ↔ Bush Beans
        # Lovage / Valerian (attractor plants)
        (96,  1),  # Lovage ↔ Tomato
        (97,  1),  # Valerian ↔ Tomato
        # Chervil
        (100,  3), # Chervil ↔ Carrot
        (100, 21), # Chervil ↔ Radish

        # --- TREES ---
        # Olive guild (Mediterranean — loves rosemary, lavender, thyme)
        (101, 32),  # Olive ↔ Rosemary
        (101, 35),  # Olive ↔ Lavender
        (101, 33),  # Olive ↔ Thyme
        (101, 82),  # Olive ↔ Red Clover    (ground cover fixes nitrogen)
        # Hazelnut
        (103, 82),  # Hazelnut ↔ Red Clover
        (103, 83),  # Hazelnut ↔ White Clover
        (103, 40),  # Hazelnut ↔ Comfrey
        # Almond
        (104, 35),  # Almond ↔ Lavender     (attracts pollinators)
        (104, 86),  # Almond ↔ Phacelia
        # Mulberry
        (105, 82),  # Mulberry ↔ Red Clover
        (105, 40),  # Mulberry ↔ Comfrey
        # Citrus guild
        (106,  2),  # Lemon ↔ Basil
        (106, 38),  # Lemon ↔ Nasturtium    (trap crop for aphids)
        (107,  2),  # Orange ↔ Basil
        (107, 38),  # Orange ↔ Nasturtium
        # Pomegranate
        (108,  2),  # Pomegranate ↔ Basil
        (108,  6),  # Pomegranate ↔ Marigold
        # Black Locust (nitrogen fixer — benefits neighbours)
        (110, 66),  # Black Locust ↔ Grape
        (110, 55),  # Black Locust ↔ Strawberry
        # Alder (nitrogen fixer)
        (111, 56),  # Alder ↔ Raspberry
        (111, 60),  # Alder ↔ Black Currant
        # Hawthorn (wildlife hedge — benefits most soft fruit)
        (112, 56),  # Hawthorn ↔ Raspberry
        (112, 58),  # Hawthorn ↔ Elderberry
        # Serviceberry
        (114, 82),  # Serviceberry ↔ Red Clover
        (114, 40),  # Serviceberry ↔ Comfrey
        # Bay Laurel
        (116,  1),  # Bay Laurel ↔ Tomato   (repels caterpillars)
        (116, 49),  # Bay Laurel ↔ Potato
        (116, 23),  # Bay Laurel ↔ Cabbage

        # --- BUSHES ---
        # Blackberry
        (117, 40),  # Blackberry ↔ Comfrey
        (117, 82),  # Blackberry ↔ Red Clover
        # Aronia
        (118, 83),  # Aronia ↔ White Clover
        (118, 40),  # Aronia ↔ Comfrey
        # Goji Berry
        (119, 35),  # Goji ↔ Lavender
        (119, 82),  # Goji ↔ Red Clover
        # Rugosa Rose
        (120,  5),  # Rugosa Rose ↔ Garlic  (repels aphids on rose)
        (120, 35),  # Rugosa Rose ↔ Lavender
        (120, 46),  # Rugosa Rose ↔ Chives
        # Sea Buckthorn (nitrogen fixer)
        (121, 55),  # Sea Buckthorn ↔ Strawberry
        (121, 82),  # Sea Buckthorn ↔ Red Clover
        # Siberian Pea Shrub (nitrogen fixer)
        (122, 56),  # Siberian Pea Shrub ↔ Raspberry
        (122, 57),  # Siberian Pea Shrub ↔ Blueberry
        # Autumn Olive (nitrogen fixer)
        (123, 55),  # Autumn Olive ↔ Strawberry
        (123, 56),  # Autumn Olive ↔ Raspberry
        # Jostaberry (gooseberry × blackcurrant hybrid)
        (124, 40),  # Jostaberry ↔ Comfrey
        (124, 83),  # Jostaberry ↔ White Clover
        # Buffaloberry (nitrogen fixer)
        (125, 55),  # Buffaloberry ↔ Strawberry
        (125, 82),  # Buffaloberry ↔ Red Clover
    ]

    execute_values(cur, """
        INSERT INTO companion_plants (plant_id, companion_plant_id)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, make_bidirectional(raw_pairs))


def seed_antagonists(cur):
    """
    Permaculture antagonist pairs — plants that inhibit each other
    via allelopathy, shared pests/diseases, or resource competition.
    """
    raw_pairs = [
        # Fennel: strongly allelopathic to almost everything
        (30,  1),  # Fennel × Tomato
        (30,  3),  # Fennel × Carrot
        (30,  8),  # Fennel × Cucumber
        (30,  7),  # Fennel × Bell Pepper
        (30, 11),  # Fennel × Pole Beans
        (30, 12),  # Fennel × Bush Beans
        (30, 16),  # Fennel × Lettuce
        (30, 88),  # Fennel × Coriander     (close relatives, cross-pollinate & inhibit)
        # Tomato
        (1,  23),  # Tomato × Cabbage       (inhibit each other)
        (1,  14),  # Tomato × Corn          (share earworm/hornworm)
        (1,  49),  # Tomato × Potato        (share blight Phytophthora infestans)
        # Alliums inhibit legumes
        (4,  11),  # Onion × Pole Beans
        (4,  12),  # Onion × Bush Beans
        (4,  13),  # Onion × Peas
        (5,  11),  # Garlic × Pole Beans
        (5,  12),  # Garlic × Bush Beans
        (5,  13),  # Garlic × Peas
        (47, 11),  # Leek × Pole Beans
        (47, 13),  # Leek × Peas
        (48, 11),  # Shallot × Pole Beans
        (48, 13),  # Shallot × Peas
        # Cabbage
        (23, 55),  # Cabbage × Strawberry   (brassica root exudates harm strawberry)
        (23,  1),  # Cabbage × Tomato
        # Potato
        (49,  8),  # Potato × Cucumber      (shared pests)
        (49, 15),  # Potato × Sunflower     (sunflower secretions inhibit potato)
        # Beet
        (20, 11),  # Beet × Pole Beans
        (20, 12),  # Beet × Bush Beans
        # Dill (when bolting / in flower)
        (29,  3),  # Dill × Carrot          (cross-pollinate, volatile inhibition)
        # Asparagus
        (52,  4),  # Asparagus × Onion
        (52,  5),  # Asparagus × Garlic
        # Mint — allelopathic, suppresses neighbours when not containerised
        (31,  3),  # Mint × Carrot
        (31, 28),  # Mint × Parsley
        # Jerusalem artichoke — extremely competitive
        (51,  1),  # Jerusalem Artichoke × Tomato
        (51, 15),  # Jerusalem Artichoke × Sunflower
        # Turnip
        (22, 11),  # Turnip × Pole Beans
        # Eggplant
        (67, 13),  # Eggplant × Peas
        # Mustard (when decomposing releases glucosinolates)
        (87, 11),  # Mustard × Pole Beans
        # Sunflower allelopathy
        (15,  3),  # Sunflower × Carrot

        # --- TREES ---
        # Walnut: produces juglone — strongly allelopathic to many plants
        (102,  1),  # Walnut × Tomato
        (102, 55),  # Walnut × Strawberry
        (102, 49),  # Walnut × Potato
        (102, 61),  # Walnut × Dwarf Apple   (stunts growth)
        (102, 56),  # Walnut × Raspberry
        (102, 57),  # Walnut × Blueberry
        (102, 117), # Walnut × Blackberry
        (102, 84),  # Walnut × Alfalfa
        # Black Locust (fast-growing, can outcompete fruit trees for light)
        (110, 103), # Black Locust × Hazelnut
        (110, 104), # Black Locust × Almond
        # Fennel vs trees (inhibits most neighbours)
        (30, 101),  # Fennel × Olive
        (30, 103),  # Fennel × Hazelnut
        # Eucalyptus-like: Jerusalem Artichoke vs trees (very competitive)
        (51, 103),  # Jerusalem Artichoke × Hazelnut
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

        print("Seeding 100 plants...")
        seed_plants(cur)

        print("Seeding companion relationships...")
        seed_companions(cur)

        print("Seeding antagonistic relationships...")
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
