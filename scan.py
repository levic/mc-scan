#!/usr/bin/env python3
import argparse
from collections import defaultdict
from itertools import chain
import logging
from pathlib import Path
import sys

import bedrock.leveldb

DEFAULT_MAX_DIST = 20
#WORLD_PATH = Path('~/minecraft/worlds/The Cameron World II (577830886)')
DEFAULT_WORLD_PATH = Path('worlds/The Cameron World II (577830886)')

logger: logging.Logger = None

Y_MIN = 1
Y_MAX = 60

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
	'minecraft:chest',
	'minecraft:diamond_ore',
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
	'iron': 'minecraft:iron_ore',
	'kelp': 'minecraft:kelp',
	'magma': 'minecraft:magma',
#	'mobspawner': 'minecraft:mob_spawner',
	'obsidian': 'minecraft:obsidian',
	'redstone': 'minecraft:redstone_ore',
	'village': (
		# this stuff you only care about if it's under the ground
		'minecraft:acacia_door',
		'minecraft:acacia_standing_sign',
		'minecraft:acacia_stairs',
		'minecraft:acacia_wall_sign',
		'minecraft:barrel',
		'minecraft:bed',
		'minecraft:bell',
		'minecraft:blast_furnace',
		'minecraft:chest',
		'minecraft:cobblestone_wall',
		'minecraft:crafting_table',
		'minecraft:diorite_stairs',
		'minecraft:double_stone_slab',
		'minecraft:fence',
		'minecraft:furnace',
		'minecraft:glass',
		'minecraft:glass_pane',
		'minecraft:grindstone',
		'minecraft:iron_bars',
		'minecraft:lantern',
		'minecraft:planks',
		'minecraft:stone_brick_stairs',
		'minecraft:stone_slab',
		'minecraft:stone_stairs',
		'minecraft:spruce_door',
		'minecraft:spruce_stairs',
		'minecraft:spruce_fence_gate',
		'minecraft:wooden_door',
	),
}

IGNORE = set([
	'minecraft:air',
	'minecraft:bedrock',
	'minecraft:blue_ice',
	'minecraft:bone_block',
	'minecraft:bubble_column',
	'minecraft:cobblestone',
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
	'minecraft:ladder',
	'minecraft:lava',
	'minecraft:leaves',
	'minecraft:leaves2',
	'minecraft:monster_egg',
	'minecraft:mossy_cobblestone',
	'minecraft:packed_ice',
	'minecraft:rail',
	'minecraft:sand',
	'minecraft:sandstone',
	'minecraft:seagrass',
	'minecraft:snow',
	'minecraft:snow_layer',
	'minecraft:stonebrick',
	'minecraft:stone',
	'minecraft:tallgrass',
	'minecraft:torch',
	'minecraft:vine',
	'minecraft:water',
	'minecraft:web',
	'minecraft:wooden_slab',

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
	'minecraft:yellow_flower',

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
	found_grouped = defaultdict(lambda: defaultdict(lambda: 0))
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

	def get_dist(x,y,z):
		dx = x - center_x
		dy = y - center_y
		dz = z - center_z
		return round((dx*dx + dy*dy + dz*dz) ** 0.5)

	def add_interesting(x, y, z, name, dv):
		found_with_dist[name].append((get_dist(x, y, z), x, y, z))
		ROUND = 4
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
				coords = chain(
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
				for y in range(y_min, y_max+1):
					block = world.getBlock(x, y, z)

					if block is None:
						continue

					name = block.name
					if name in ignore_blocks:
						continue

					dv = DV_LOOKUPS[block.name][block.dv] if block.name in DV_LOOKUPS else None
					if name in interesting_blocks:
						add_interesting(x, y, z, name, dv)
#						print(name, dv)
					else:
						print(name, dv)
						if block.nbt is not None:
							logger.error(x, y, z, block.name, block.nbt)
#							raise Exception(f'Found an NBT at {x},{y},{z}')
	return found_grouped, found_with_dist

def show_interesting(found_grouped, found_with_dist):
	for name in sorted(found_with_dist.keys()):
		total = len(found_with_dist[name])
		print('------------------------------------------------------------------------')
		print('TOTAL', name, total)
#		print(name)
#		for (x, y, z), count in found_grouped[name].items():
#			print(name, dist, (x, y, z), count)
		for dist, x, y, z in sorted(found_with_dist[name]):
			print(name, dist, '(', x, y, z, ')')

def parse():
	parser = argparse.ArgumentParser()
	parser.add_argument('center_x', type=int)
	parser.add_argument('center_y', type=int)
	parser.add_argument('center_z', type=int)
	parser.add_argument('--ymin', type=int, default=Y_MIN)
	parser.add_argument('--ymax', type=int, default=Y_MAX)
	parser.add_argument('--dist', type=int, default=DEFAULT_MAX_DIST)
	parser.add_argument('--world', type=str, default=DEFAULT_WORLD_PATH)
	parser.add_argument('--verbose', '-v', action='count', default=0, dest='log_level')
	for opt in OPTIONAL_BLOCKS:
		parser.add_argument(f'--{opt}', default=False, action='store_true')
	opts = parser.parse_args(sys.argv[1:])
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
	show_interesting(found_grouped, found_with_dist)

if __name__ == '__main__':
	run()
