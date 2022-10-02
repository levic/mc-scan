#!/usr/bin/env python3
import argparse
from collections import defaultdict
import dotenv
import functools
import itertools
import json
import logging
import os
from pathlib import Path
import sys
from typing import Tuple

import bedrock.leveldb

# time: 32x32 => 3.37 sec,
#  27k output with 4 char indent
#  13k output with no indent
#  <3k output with no indent + gzip

# TODO:
# --down
# --up
# --north
# --east
# --west
# --south
# --yrange


# ---------------------------------------------------------------------------

BlockType = str
Coords = Tuple[float, float, float]

# ---------------------------------------------------------------------------

@functools.lru_cache()
def get_config():
    config_path = Path(__file__).parent.joinpath('settings.inc')
    dotenv.load_dotenv(dotenv_path=config_path)
    config_vars = [
        'level_name',
        'source_worlds',
    ]
    return {key: os.getenv(key) for key in config_vars}


DEFAULT_MAX_DIST = 20
DEFAULT_WORLD_PATH = Path(__file__).parent.joinpath('worlds', get_config()['level_name'])

logger: logging.Logger = None

# default coordinate scans
DEFAULT_Y_MIN = -63
DEFAULT_Y_MAX = 60
# since 1.19 it seems that the lowest coordinate is now -64
# but in the DB things still start at 0 and are adjusted by -64 after loading
Y_OFFSET = 64

# bottom of the ladder
center_x = 989
center_y = 15
center_z = 55

# ---------------------------------------------------------------------------

WOOD_OAK = 0
WOOD_SPRUCE = 1
WOOD_BIRCH = 2
WOOD_JUNGLE =3 
WOOD_ACACIA = 4
WOOD_DARKOAK = 5
DV_WOOD = {
    WOOD_OAK: 'Oak',
    WOOD_SPRUCE: 'Spruce',
    WOOD_BIRCH: 'Birch',
    WOOD_JUNGLE: 'Jungle',
    WOOD_ACACIA: 'Acacia',
    WOOD_DARKOAK: 'Dark Oak',
}

STONE_STONE = 0
STONE_GRANITE = 1
STONE_GRANITEPOLISHED = 2
STONE_DIORITE = 3
STONE_DIORITEPOLISHED = 4
STONE_ANDESITE = 5
STONE_ANDESITEPOLISHED = 6
DV_STONE = {
    STONE_STONE: 'Stone',
    STONE_GRANITE: 'Granite',
    STONE_GRANITEPOLISHED: 'Polished Granite',
    STONE_DIORITE: 'Diorite',
    STONE_DIORITEPOLISHED: 'Polished Diorite',
    STONE_ANDESITE: 'Andesite',
    STONE_ANDESITEPOLISHED: 'Polished Andesite',
}

DV_LOOKUPS = {
    'minecraft:stone': DV_STONE,
    'minecraft:wood': DV_WOOD,
}

INTERESTING = set([
    'minecraft:amethyst_block',
    'minecraft:amethyst_cluster',
    'minecraft:budding_amethyst',

    'minecraft:chest',

    'minecraft:deepslate_diamond_ore',
    'minecraft:deepslate_gold_ore',
    'minecraft:deepslate_lapis_ore',
    'minecraft:diamond_ore',
    'minecraft:emerald_ore',
    'minecraft:gold_ore',
    'minecraft:lapis_ore',

    'minecraft:mob_spawner',

    'minecraft:brewing_stand',
    'minecraft:cartography_table',
    'minecraft:cauldron',
    'minecraft:wall_banner',

    'minecraft:portal',

])

OPTIONAL_BLOCKS = {
    'books': (
        'minecraft:bookshelf',
    ),
    'clay': (
        'minecraft:clay',
        'minecraft:hardened_clay',
        'minecraft:stained_hardened_clay',
    ),
    'coal': 'minecraft:coal_ore',
    'copper': (
        'minecraft:copper_ore',
        'minecraft:deepslate_copper_ore',
        ),
    'deep': (
        'minecraft:chiseled_deepslate',
        'minecraft:cracked_deepslate_bricks',
        'minecraft:cracked_deepslate_tiles',
        'minecraft:deepslate_brick_slab',
        'minecraft:deepslate_brick_stairs',
        'minecraft:deepslate_brick_wall',
        'minecraft:deepslate_bricks',
        'minecraft:deepslate_tiles',
        'minecraft:deepslate_tile_slab',
        'minecraft:deepslate_tile_stairs',
        'minecraft:polished_deepslate',
        'minecraft:polished_deepslate_stairs',
        'minecraft:polished_deepslate_wall',
        'minecraft:reinforced_deepslate',
        'minecraft:stone_block_slab4', # double check

        'minecraft:sculk',
        'minecraft:sculk_catalyst',
        'minecraft:sculk_sensor',
        'minecraft:sculk_shrieker',
        'minecraft:sculk_vein',
        'minecraft:soul_fire',
        'minecraft:soul_lantern',
    ),
    'iron': (
        'minecraft:deepslate_iron_ore',
        'minecraft:iron_ore',
    ),
    'kelp': 'minecraft:kelp',
    'lava': 'minecraft:lava',
    'magma': 'minecraft:magma',
    'obsidian': 'minecraft:obsidian',
    'redstone': (
        'minecraft:deepslate_redstone_ore',
        'minecraft:redstone_ore',
    ),
    'treasure': (
    ),
    'village': (
        # this stuff you only care about if it's under the ground
        'minecraft:acacia_door',
        'minecraft:acacia_stairs',
        'minecraft:barrel',
        'minecraft:bed',
        'minecraft:bell',
        'minecraft:blast_furnace',
        'minecraft:cobblestone_wall',
        'minecraft:composter',
        'minecraft:crafting_table',
        'minecraft:diorite_stairs',
        'minecraft:double_stone_slab',
        'minecraft:furnace',
        'minecraft:glass',
        'minecraft:glass_pane',
        'minecraft:grindstone',
        'minecraft:iron_bars',
        'minecraft:lantern',
        'minecraft:rail',
        'minecraft:stone_brick_stairs',
        'minecraft:stone_slab',
        'minecraft:stone_stairs',
        'minecraft:spruce_door',
        'minecraft:spruce_stairs',
        'minecraft:spruce_fence_gate',
        'minecraft:stonecutter_block',
        'minecraft:wooden_door',
    ),
}

IGNORE = set([
    'minecraft:air',
    'minecraft:bamboo',
    'minecraft:bedrock',
    'minecraft:blue_ice',
    'minecraft:bone_block',
    'minecraft:bubble_column',
    'minecraft:calcite',
    'minecraft:candle',
    'minecraft:carpet',
    'minecraft:cobblestone',
    'minecraft:cobbled_deepslate',
    'minecraft:deepslate',
    'minecraft:dirt',
    'minecraft:double_plant',
    'minecraft:double_wooden_slab',
    'minecraft:farmland',
    'minecraft:flowing_lava',
    'minecraft:flowing_water',
    'minecraft:grass',
    'minecraft:grass_path',
    'minecraft:gravel',
    'minecraft:ice',
    'minecraft:leaves',
    'minecraft:leaves2',
    'minecraft:monster_egg',
    'minecraft:mossy_cobblestone',
    'minecraft:packed_ice',
    'minecraft:raw_iron_block',
    'minecraft:sand',
    'minecraft:sandstone',
    'minecraft:seagrass',
    'minecraft:smooth_basalt', # seems to only occur with amethyst?
    'minecraft:snow',
    'minecraft:snow_layer',
    'minecraft:stonebrick',
    'minecraft:stone',
    'minecraft:tallgrass',
    'minecraft:torch',
    'minecraft:tuff',
    'minecraft:vine',
    'minecraft:water',
    'minecraft:web',
    'minecraft:wool',

    # constructed
    'minecraft:acacia_standing_sign',
    'minecraft:acacia_wall_sign',
    'minecraft:fence',
    'minecraft:hopper',
    'minecraft:ladder',
    'minecraft:lectern',
    'minecraft:lever',
    'minecraft:lit_redstone_lamp',
    'minecraft:lit_deepslate_redstone_ore',
    'minecraft:planks',
    'minecraft:powered_comparator',
    'minecraft:powered_repeater',
    'minecraft:redstone_block',
    'minecraft:redstone_lamp',
    'minecraft:redstone_wire',
    'minecraft:sticky_piston',
    'minecraft:unlit_redstone_torch',
    'minecraft:unpowered_comparator',
    'minecraft:unpowered_repeater',
    'minecraft:wooden_slab',


    # flowers
    'minecraft:red_flower',
    'minecraft:yellow_flower',
    
    # logs
    'minecraft:deadbush',
    'minecraft:log',
    'minecraft:log2',
    'minecraft:stripped_spruce_log',
    'minecraft:wood',

    # food
    'minecraft:hay_block',

    'minecraft:beetroot',
    'minecraft:carrots',
    'minecraft:melon_block',
    'minecraft:melon_stem',
    'minecraft:wheat',

    # mushrooms
    'minecraft:brown_mushroom',
    'minecraft:red_mushroom',

    # lush caves
    'minecraft:big_dripleaf',
    'minecraft:cave_vines',
    'minecraft:cave_vines_body_with_berries',
    'minecraft:cave_vines_head_with_berries',
    'minecraft:glow_lichen',
    'minecraft:moss_block',
    'minecraft:moss_carpet',
    'minecraft:small_dripleaf_block',
    'minecraft:spore_blossom',

    # nether
    'minecraft:soul_sand',
])

def init_logger(log_level: int) -> logging.Logger:
    levels = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG
    }
    level = levels[min(len(levels), log_level)]
    logging.basicConfig(level=level, format='%(levelname)-8s %(message)s')
    logger = logging.getLogger('mc-scan')
    return logger


def scan(center, y_range, max_dist, world_path, optional_blocks_chosen):
    center_x, center_y, center_z = center
    y_min, y_max = y_range
    found_grouped: Dict[Block, Dict[Coords, int]] = defaultdict(lambda: defaultdict(lambda: 0))
    found_with_dist = defaultdict(list)

    interesting_blocks = INTERESTING.copy()
    ignore_blocks = IGNORE.copy()
    for key, value in optional_blocks_chosen.items():
        blocks = OPTIONAL_BLOCKS[key]
        if isinstance(blocks, str):
            blocks = (blocks,)
        for block in blocks:
            if value:
                interesting_blocks.add(block)
            else:
                ignore_blocks.add(block)

    def get_dist(x,y,z, metric='MANHATTAN_ADJUSTED'):
        dx = x - center_x
        dy = y - center_y
        dz = z - center_z

        if metric == 'MANHATTAN':
            return abs(dx) + abs(dy) + abs(dz)

        if metric == 'MANHATTAN_ADJUSTED':
            # a horizontal traversal requires 2 blocks
            # but vertical usually requires at least 3 blocks (on average a bit more)
            return (abs(dx)*2 + abs(dy)*3.25 + abs(dz)*2)/2

        if metric == 'EUCLIDEAN':
            return round((dx*dx + dy*dy + dz*dz) ** 0.5)

        raise Exception(f'Unknown distance metric {metric}')

    def add_interesting(x, y, z, name, dv):
        if name.startswith('minecraft:deepslate_'):
            name = name[:len('minecraft:')] + name[len('minecraft:deepslate_'):]
        found_with_dist[name].append((get_dist(x, y, z), x, y, z))
        ROUND = 1
        x = x - (x % ROUND)
        y = y - (y % ROUND)
        z = z - (z % ROUND)
        found_grouped[name][(x, y, z)] += 1
        #print(found_with_dist[name])

    with bedrock.World(world_path) as world:
        for dist in range(0, max_dist+1):
            logger.info(f'Dist {dist}')
            if dist == 0:
                coords = ((center_x, center_z), )
            else:
                coords = itertools.chain(
                    # top
                    ((x, center_z-dist) for x in range(center_x-dist, center_x+dist+1)),
                    # bottom
                    ((x, center_z+dist) for x in range(center_x-dist, center_x+dist+1)),
                    # left
                    ((center_x-dist, z) for z in range(center_z-dist+1, center_z+dist+1-1)),
                    # right
                    ((center_x+dist, z) for z in range(center_z-dist+1, center_z+dist+1-1)),
                )
            for x, z in coords:
                logger.debug(f'  Check {x}, *, {z}')
                for y in range(y_min, y_max+1):
                    # this offset matches Amulet's view of the world
#                   y_db = y - Y_OFFSET
                    y_db = y
                    logger.debug(f'  Check {x}, {y} {y_db}, {z}')
                    block = world.getBlock(x, y_db, z)

                    if block is None:
                        #print(f'  block {block}')
                        continue

                    name = block.name
                    #print(f'  block {name}')
                    if name in ignore_blocks:
                        continue

                    dv = DV_LOOKUPS[block.name][block.dv] if block.name in DV_LOOKUPS else None
                    #print(f'    dv {dv}')
                    if name in interesting_blocks:
                        add_interesting(x, y, z, name, dv)
#                        print(name, dv)
                    else:
                        logger.error(f'Unrecognised block {name}/{dv}')
#                        print(name, dv)
                        if block.nbt is not None:
                            logger.error(x, y, z, block.name, block.nbt)
#                            raise Exception(f'Found an NBT at {x},{y},{z}')
    return found_grouped, found_with_dist

def show_interesting_text(found_grouped, found_with_dist):
    for name in sorted(found_with_dist.keys()):
        total = len(found_with_dist[name])
        print('------------------------------------------------------------------------')
        print('TOTAL', name, total)
        for dist, x, y, z in sorted(found_with_dist[name]):
            print(name, dist, '(', x, y, z, ')')

def show_interesting_text_closest(found_grouped, found_with_dist):
    merged_list = []
    for name in sorted(found_with_dist.keys()):
        merged_list += [ (dist, name, x, y, z) for dist, x, y, z in found_with_dist[name] ]
    merged_list.sort()

    total = len(merged_list)
    print('------------------------------------------------------------------------')
    print('TOTAL', total)
    for dist, name, x, y, z in merged_list:
        print(name, dist, '(', x, y, z, ')')


def show_interesting_json(found_grouped, found_with_dist):
    data = {}
    for block_name, coords_count in found_grouped.items():
        if block_name not in data:
            data[block_name] = {}
        for (x,y,z), count in coords_count.items():
            if f"{x},{z}" not in data[block_name]:
                data[block_name][f"{x},{z}"] = []
            data[block_name][f"{x},{z}"].append(y)
    print(json.dumps(data, indent=None))
    

def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('center_x', type=str)
    parser.add_argument('center_y', type=str)
    parser.add_argument('center_z', type=str)
    parser.add_argument('--ymin', type=int, default=DEFAULT_Y_MIN)
    parser.add_argument('--ymax', type=int, default=DEFAULT_Y_MAX)
    parser.add_argument('--dist', type=int, default=DEFAULT_MAX_DIST)
    parser.add_argument('--world', type=str, default=DEFAULT_WORLD_PATH)
    parser.add_argument('--verbose', '-v', action='count', default=0, dest='log_level')
    parser.add_argument('--json', action='store_const', default='text', const='json', dest='format')
    parser.add_argument('--closest', action='store_const', default='text', const='text_closest', dest='format')
    for opt in OPTIONAL_BLOCKS:
        parser.add_argument(f'--{opt}', default=False, action='store_true')
    opts = parser.parse_args(sys.argv[1:])
    opts.center_x = int(opts.center_x.rstrip(','))
    opts.center_y = int(opts.center_y.rstrip(','))
    opts.center_z = int(opts.center_z.rstrip(','))
    return opts

def run():
    opts = parse()
    global logger
    logger = init_logger(opts.log_level)
    found_grouped, found_with_dist = scan(
        (opts.center_x, opts.center_y, opts.center_z),
        (opts.ymin, opts.ymax),
        opts.dist,
        opts.world,
        { key: getattr(opts, key) for key in OPTIONAL_BLOCKS },
    )
    show_fns = {
        'text': show_interesting_text,
        'text_closest': show_interesting_text_closest,
        'json': show_interesting_json,
    }
    show_fns[opts.format](found_grouped, found_with_dist)

if __name__ == '__main__':
    run()
