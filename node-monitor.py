#!/usr/bin/python

import argparse
import json
import inspect, os

def main():
	script_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + '/'# script directory

	parser = argparse.ArgumentParser(description='Consumes VCMP JSON in search of the status of a given virtual server\'s pool members')

	parser.add_argument('VIP_IP', help='full IP address of the VIP')
	parser.add_argument('VIP_PORT', help='Port that the VIP should be listening on')
	parser.add_argument('--folder',help='Absolute path to folder containing the vcmp json files (with trailing slash).  Defaults to current working directory.', default=script_path)
	
	args = parser.parse_args()
	
	#open all 3 files, parse them, grab the items
	vs_file = open(args.folder+"vcmp-virtual-servers.json")
	pools_file = open(args.folder+"vcmp-pools.json")
	pool_members_file = open(args.folder+"vcmp-pool-members.json")

	vs_obj = json.load(vs_file)
	pools_obj = json.load(pools_file)
	pool_members_obj = json.load(pool_members_file)

	vs_items = vs_obj['items']
	pools_items = pools_obj['items']
	pool_members_items = pool_members_obj['items']

	#use the ip and port in the virtual servers list 
	#to find a virtual server we're looking for
	#save its corresponding pool reference ID
	pool_ref = None
	for item in vs_items:
		if item['address'] == args.VIP_IP and item['port'] == int(args.VIP_PORT):
			#print item['name']
			pool_ref = int(item['poolReference']['link'].split('/')[-1])
			#print "pool ref: "+str(pool_ref)

	if pool_ref is None:
		print "no Virtual Server found with IP "+args.VIP_IP+" and Port "+args.VIP_PORT
		exit()

	#use the pool reference ID to find the right pool in the list of pools
	#pull out the list of members in the pool and 
	#store their reference IDs
	members_refs = []
	for item in pools_items:
		if item['objectId'] == pool_ref:
			for link_obj in item['poolMemberReferences']:
				member_ref = int(link_obj['link'].split('/')[-1])
				#print "member ref: "+str(member_ref)
				members_refs.append(member_ref)
	#print members_refs

	if len(members_refs) == 0:
		print "no members found in pool "+str(pool_ref)+" denoted by IP "+args.VIP_IP+" and Port "+args.VIP_PORT


	#look through the list of pool members for any
	#with a reference ID that we stored earlier in members_refs
	#if the health is listed as red, increment the counter
	#and print out it's name
	num_red = 0
	for item in pool_members_items:
		if item['objectId'] in members_refs:
			for stat in item['statsContext']['stats']:
				if stat['name'] == 'health':
					#print stat['description']
					status = stat['description'].split(": ")[-1]
					if status == "AVAIL_RED":
						num_red+=1
						print "node name "+item['name']+" is RED"

	print "number of red nodes "+str(num_red)

if __name__ == '__main__':
	main()
