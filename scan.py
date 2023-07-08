#!/usr/bin/env python3
import argparse
from collections import defaultdict
from datetime import datetime
import dotenv
import functools
import humanize
import itertools
import json
import logging
import os
from pathlib import Path
import sys
from typing import Tuple

bedrock_path = Path(__file__).parent.parent / "bedrock"
if not bedrock_path.exists() or not bedrock_path.is_dir():
    raise RuntimeError(f'bedrock library not found at {bedrock_path}')
sys.path[1:1] = [str(bedrock_path)]
import bedrock.leveldb

# timings for potential future json output
# time: 32x32 => 3.37 sec,
#  27k output with 4 char indent
#  13k output with no indent
#  <3k output with no indent + gzip

# ---------------------------------------------------------------------------

BlockGroupType = str
BlockType = str
Coords = Tuple[int, int, int]
DistCoords = Tuple[float, int, int, int]

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

# y coordinate ranges
Y_MIN = -63
Y_MAX = 319

# default coordinate scans
DEFAULT_Y_MIN = -63
DEFAULT_Y_MAX = 60
DEFAULT_Y_DIST = 40

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

INTERESTING: set[BlockType] = {
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

}

OPTIONAL_BLOCKS: dict[BlockGroupType, set[BlockType]] = {
    'amethyst': {
        'minecraft:amethyst_block',
        'minecraft:amethyst_cluster',
        'minecraft:budding_amethyst',
        'minecraft:small_amethyst_bud',
        'minecraft:medium_amethyst_bud',
        'minecraft:large_amethyst_bud',
    },
    'books': {
        'minecraft:bookshelf',
    },
    'clay': {
        'minecraft:clay',
        'minecraft:hardened_clay',
        'minecraft:stained_hardened_clay',
    },
    'coal': {
        'minecraft:coal_ore',
        'minecraft:deepslate_coal_ore',
    },
    'copper': {
        'minecraft:copper_ore',
        'minecraft:deepslate_copper_ore',
        'minecraft:raw_copper_block',
    },
    'deep': {
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
    },
    'iron': {
        'minecraft:deepslate_iron_ore',
        'minecraft:iron_ore',
    },
    'kelp': 'minecraft:kelp',
    'lava': 'minecraft:lava',
    'magma': 'minecraft:magma',
    'obsidian': 'minecraft:obsidian',
    'redstone': {
        'minecraft:deepslate_redstone_ore',
        'minecraft:redstone_ore',
    },
    'treasure': {
    },
    'village': {
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
    },
}

IGNORE: set[BlockType] = {
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
    'minecraft:jungle_fence',
    'minecraft:jungle_fence_gate',
    'minecraft:ladder',
    'minecraft:lectern',
    'minecraft:lever',
    'minecraft:lit_redstone_lamp',
    'minecraft:lit_deepslate_redstone_ore',
    'minecraft:normal_stone_stairs',
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
}

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


def scan(
    center: int,
    x_range: int,
    y_range: int,
    z_range: int,
    max_dist: int,
    world_path: Path,
    optional_blocks_chosen: dict[BlockGroupType, bool]
):
    center_x, center_y, center_z = center
    x_min, x_max = x_range
    y_min, y_max = y_range
    z_min, z_max = z_range
    found_grouped: dict[BlockType, dict[Coords, int]] = defaultdict(lambda: defaultdict(lambda: 0))
    found_with_dist: dict[BlockType, list[DistCoords]] = defaultdict(list)

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

    def get_dist(x: int, y: int, z: int, metric='MANHATTAN_ADJUSTED') -> float:
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

    def add_interesting(x: int, y: int, z: int, name: BlockType, dv: str):
        if name.startswith('minecraft:deepslate_'):
            name = name[:len('minecraft:')] + name[len('minecraft:deepslate_'):]
        found_with_dist[name].append((get_dist(x, y, z), x, y, z))
        ROUND = 1
        x = x - (x % ROUND)
        y = y - (y % ROUND)
        z = z - (z % ROUND)
        found_grouped[name][(x, y, z)] += 1
        #print(found_with_dist[name])

#    seen = set()

    with bedrock.World(world_path) as world:
        for dist in range(0, max_dist+1):
            logger.info(f'Dist {dist}')
            if dist == 0:
                coords = ((center_x, center_z), )
            else:
                top = []
                bottom = []
                left = []
                right = []

                z_top = center_z - dist
                top = \
                    ((x, z_top) for x in range(
                        max(center_x-dist, x_min),
                        min(center_x+dist+1, x_max+1),
                    )) if z_top >= z_min else []

                z_bottom = center_z + dist
                bottom = \
                    ((x, z_bottom) for x in range(
                        max(center_x-dist, x_min),
                        min(center_x+dist+1, x_max+1),
                    )) if z_bottom <= z_max else []

                x_left = center_x - dist
                left = \
                    ((x_left, z) for z in range(
                        max(center_z-dist+1, z_min),
                        min(center_z+dist+1-1, z_max+1),
                    )) if x_left >= x_min else []

                x_right = center_x + dist
                right = \
                    ((x_right, z) for z in range(
                        max(center_z-dist+1, z_min),
                        min(center_z+dist+1-1, z_max+1),
                    )) if x_right <= x_max else []

                coords = itertools.chain(top, bottom, left, right)

            for x, z in coords:
                logger.debug(f'  Check {x:4},    *, {z:4}')
#                assert (x,z) not in seen
#                seen.add((x,z))
                for y in range(y_min, y_max+1):
#                    logger.debug(f'        {x:4}, {y:4}, {z:4}')
                    block = world.getBlock(x, y, z)

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

    '''
    for z in range(100-2, 100+2+1):
        for x in range(100-2, 100+2+1):
            if (x, z) == (center_x, center_y):
                symbol = 'o'
            elif (x, z) in seen:
                symbol = 'x'
            else:
                symbol = '.'
            print(symbol, end='')
        print("\n")
    '''

    return found_grouped, found_with_dist

def show_interesting_text(
    found_grouped: dict[BlockType, dict[Coords, int]],
    found_with_dist: dict[BlockType, list[DistCoords]],
):
    for name in sorted(found_with_dist.keys()):
        total = len(found_with_dist[name])
        print('------------------------------------------------------------------------')
        print('TOTAL', name, total)
        for dist, x, y, z in sorted(found_with_dist[name]):
            print(name, f'{dist:6} ({x:4} {y:4} {z:4})')

def show_interesting_text_closest(
    found_grouped: dict[BlockType, dict[Coords, int]],
    found_with_dist: dict[BlockType, list[DistCoords]],
):
    merged_list = []
    for name in sorted(found_with_dist.keys()):
        merged_list += [ (dist, name, x, y, z) for dist, x, y, z in found_with_dist[name] ]
    merged_list.sort()

    total = len(merged_list)
    print('------------------------------------------------------------------------')
    print('TOTAL', total)
    for dist, name, x, y, z in merged_list:
        print(name, dist, '(', x, y, z, ')')


def show_interesting_json(
    found_grouped: dict[BlockType, dict[Coords, int]],
    found_with_dist: dict[BlockType, list[DistCoords]],
):
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
    parser.add_argument('--ymin', type=int, default=None)
    parser.add_argument('--ymax', type=int, default=None)
    parser.add_argument('--dist', type=int, default=DEFAULT_MAX_DIST)
    parser.add_argument('--world', type=Path, default=DEFAULT_WORLD_PATH)
    parser.add_argument('--verbose', '-v', action='count', default=0, dest='log_level')
    parser.add_argument('--json', action='store_const', default='text', const='json', dest='format')
    parser.add_argument('--closest', action='store_const', default='text', const='text_closest', dest='format')
    parser.add_argument('--up', action='store_true')
    parser.add_argument('--down', action='store_true')
    parser.add_argument('--ydist', type=int, default=None)
    parser.add_argument('--north', action='store_true')
    parser.add_argument('--south', action='store_true')
    parser.add_argument('--east', action='store_true')
    parser.add_argument('--west', action='store_true')
    for opt in OPTIONAL_BLOCKS:
        parser.add_argument(f'--{opt}', default=False, action='store_true')

    opts = parser.parse_args(sys.argv[1:])
    opts.center_x = int(opts.center_x.rstrip(','))
    opts.center_y = int(opts.center_y.rstrip(','))
    opts.center_z = int(opts.center_z.rstrip(','))

    if opts.east and opts.west:
        raise Exception('--east and --west are mutually exclusive')
    if opts.north and opts.south:
        raise Exception('--north and --south are mutually exclusive')

    ymax_candidates = [
        opts.ymax,
        opts.center_y if opts.down else None,
        opts.center_y + opts.ydist if opts.ydist is not None else None,
        max(DEFAULT_Y_MAX, opts.center_y + DEFAULT_Y_DIST)
    ]
    opts.ymax = next(y for y in ymax_candidates if y is not None)
    opts.ymax = min(opts.ymax, Y_MAX)

    ymin_candidates = [
        opts.ymin,
        opts.center_y if opts.up else None,
        opts.center_y - opts.ydist if opts.ydist is not None else None,
        min(DEFAULT_Y_MIN, opts.center_y - DEFAULT_Y_DIST)
    ]
    opts.ymin = next(y for y in ymin_candidates if y is not None)
    opts.ymin = max(Y_MIN, opts.ymin)

    return opts

def show_age(world_path: Path):
    # reading the dir is not good because the act of opening the file
    # sets a new modified timestamp
    #world_db = Path(world_path, 'db')
    #now = datetime.now()
    #smallest_delta = None
    #for f in world_db.iterdir():
    #    if not f.is_file():
    #        continue
    #    t = datetime.fromtimestamp(f.stat().st_mtime)
    #    delta = now - t
    #    smallest_delta = delta if smallest_delta is None else min(smallest_delta, delta)

    smallest_delta = datetime.now() - datetime.fromtimestamp((world_path / 'last_updated').stat().st_mtime)
    print('Last updated:', humanize.precisedelta(smallest_delta))
    

def run():
    opts = parse()
    global logger
    logger = init_logger(opts.log_level)

    show_age(Path(opts.world))

    x_min = opts.center_x - (opts.dist if not opts.east else 0)
    x_max = opts.center_x + (opts.dist if not opts.west else 0)
    z_min = opts.center_z - (opts.dist if not opts.south else 0)
    z_max = opts.center_z + (opts.dist if not opts.north else 0)

    logger.info('Searching'
       f' [{x_min}-{x_max}]'
       f' [{opts.ymin}-{opts.ymax}]'
       f' [{z_min}-{z_max}]'
       )

    found_grouped, found_with_dist = scan(
        (opts.center_x, opts.center_y, opts.center_z),
        (x_min, x_max),
        (opts.ymin, opts.ymax),
        (z_min, z_max),
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
