#!/usr/bin/env python2
import subprocess
import re
import os
import sys
import time
import socket
import shutil
import configparser
import thread
import threading
import multiprocessing
from datetime import datetime


configfile="/etc/node-exporter-borg-stats.ini"
textfile_collector_dir="/var/lib/prometheus/node-exporter"

def calc_bytes(value, unit):
	if unit=='kB':
		return value * 1024
	elif unit=='MB':
		return value * 1024 * 1024
	elif unit=='GB':
		return value * 1024 * 1024 * 1024
	elif unit=='TB':
		return value * 1024 * 1024 * 1024 * 1024

def print_prom(file, hostname, archive, parameter, value):
    file.write(parameter+"{host=\""+hostname+"\", archive=\""+archive+"\"} "+str(value)+"\n")

def borg_repo_check(**kwargs):
#def borg_repo_check(repo, repokey, metric_name, sshargs):
	borg_repo = None
	borg_repo_key = None
	metric_name = None
	hostname = None
	sshargs = None

	for key, value in kwargs.items():
		if key == "repo":
			borg_repo=value
		if key == "repokey":
			borg_repo_key=value
		if key == "metric_name":
			metric_name=value
		if key == "hostname":
			hostnameval=value
		if key == "sshargs":
			sshargs=value

	if borg_repo is None:
		print("ERROR: Borg Repo is required.")
		return

	if borg_repo_key is None:
		print("ERROR: Repokey is required.")
		return
	else:
		os.environ["BORG_PASSPHRASE"] = borg_repo_key

	if hostname is None:
		hostname=socket.gethostname()
	else:
		hostname=hostnameval

	if metric_name is None:
		print("ERROR: metric_name is required.")
		return

	if sshargs is not None:
		os.environ["BORG_RSH"] = sshargs

	tmp_file_name = textfile_collector_dir+"/"+metric_name+".tmp"
	prom_file_name = textfile_collector_dir+"/"+metric_name+".prom"

	cmd_borg_list=["borg","list", borg_repo]
	proc_borg_list = subprocess.Popen(cmd_borg_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	proc_borg_list.wait()

	if proc_borg_list.returncode != 0:
		for line in proc_borg_list.stderr.readlines():
			m = re.search("passphrase supplied .* is incorrect.", line)
			if m is not None:
				print("ERROR: Incorrect Borg repokey for repo " + borg_repo)
			else:
				print(line)
		return



	archives = {}
	count_archives = 0

	for archive in proc_borg_list.stdout.readlines():
		#print "Raw: "+archive
		m=re.search(r"^(?P<archive>\S+)-(?P<date>\d{4}-\d{2}-\d{2})\S+(?P<time>\d{2}:\d{2}:\d{2})\S*\s", archive)
		m2=re.search(r"^(?P<name>\S+)\s", archive)
		if m is not None:
			count_archives = count_archives+1

			this_archive={'name':m2.group('name'), 'datetime':datetime.strptime(m.group('date')+" "+m.group('time'), '%Y-%m-%d %H:%M:%S')}

			if m.group('archive') in archives:
				# An archive with the same name exists, we need to check which is the more recent
				if archives[m.group('archive')]['datetime']<this_archive['datetime']:
					archives[m.group('archive')]=this_archive

			else:
				# No archive exists for this name, we add it.
				archives[m.group('archive')]=this_archive

	print("Repo " + borg_repo +": " + str(len(archives))+" different archives")
	print("Repo " + borg_repo +": " + str(count_archives)+" archives in total")

	#Create empty tmp file
	tmp_file = open(tmp_file_name,"w")

	for archive, value in archives.iteritems():
		archive_name = value['name']
		archive_datetime=value['datetime']

		print("Repo " + borg_repo  + ": upating "+archive+" from archive "+archive_name)

		print_prom(tmp_file, hostname, archive, "borg_backup_last_update_"+metric_name, time.mktime(archive_datetime.timetuple()))

		cmd_borg_info=["borg","info",borg_repo+"::"+archive_name]
		proc_borg_info = subprocess.Popen(cmd_borg_info, stdout=subprocess.PIPE)

		for line in proc_borg_info.stdout.readlines():
			m=re.search("Number of files: (?P<files_number>\d*)", line)
			if m:
				print_prom(tmp_file, hostname, archive, "borg_backup_files_"+metric_name, m.group('files_number'))

			m=re.search("Chunk index:\s*(?P<chunk_index_unique>\d*)\s*(?P<chunk_index_total>\d*)", line)
			if m:
				print_prom(tmp_file, hostname, archive, "borg_backup_chunks_unique_"+metric_name, m.group('chunk_index_unique'))
				print_prom(tmp_file, hostname, archive, "borg_backup_chunks_total_"+metric_name, m.group('chunk_index_total'))

			m=re.search("This archive:\s*(?P<original_size>\d*.\d*)\s(?P<original_size_unit>[A-Za-z]{2})\s*(?P<compressed_size>\d*.\d*)\s(?P<compressed_size_unit>[A-Za-z]{2})\s*(?P<total_size>\d*.\d*)\s(?P<total_size_unit>[A-Za-z]{2})", line)
			if m:
				print_prom(tmp_file, hostname, archive, "borg_backup_last_size_"+metric_name, calc_bytes(float(m.group('original_size')), m.group('original_size_unit')))
				print_prom(tmp_file, hostname, archive, "borg_backup_last_size_compressed_"+metric_name, calc_bytes(float(m.group('compressed_size')), m.group('compressed_size_unit')))
				print_prom(tmp_file, hostname, archive, "borg_backup_last_size_dedup_"+metric_name, calc_bytes(float(m.group('total_size')), m.group('total_size_unit')))

			m=re.search("All archives:\s*(?P<original_size>\d*.\d*)\s(?P<original_size_unit>[A-Za-z]{2})\s*(?P<compressed_size>\d*.\d*)\s(?P<compressed_size_unit>[A-Za-z]{2})\s*(?P<total_size>\d*.\d*)\s(?P<total_size_unit>[A-Za-z]{2})", line)
			if m:
				print_prom(tmp_file, hostname, archive, "borg_backup_total_size_"+metric_name, calc_bytes(float(m.group('original_size')), m.group('original_size_unit')))
				print_prom(tmp_file, hostname, archive, "borg_backup_total_size_compressed_"+metric_name, calc_bytes(float(m.group('compressed_size')), m.group('compressed_size_unit')))
				print_prom(tmp_file, hostname, archive, "borg_backup_total_size_dedup_"+metric_name, calc_bytes(float(m.group('total_size')), m.group('total_size_unit')))

	print("Repo " + borg_repo + ": Complete.")
	tmp_file.close()
	shutil.move(tmp_file_name, prom_file_name)



config = configparser.ConfigParser()


try:
	with open (configfile) as f:
		config.read_file(f)
except IOError:
	raise ValueError, "config file does not exist"



jobs = []
for metric in config.sections():
	crepo = ""
	crepokey = ""
	csshargs = ""
	if config[metric]['repo']:
		crepo = config[metric]['repo']
	if config[metric]['repokey']:
		crepokey = config[metric]['repokey']
	if config[metric]['sshargs']:
		csshargs = config[metric]['sshargs']
	kwargsX = {"repo": crepo, "repokey": crepokey, "metric_name": metric, "sshargs" :csshargs}


	p = multiprocessing.Process(target=borg_repo_check, args=(), kwargs=kwargsX)
	p.start()
	time.sleep(1)

