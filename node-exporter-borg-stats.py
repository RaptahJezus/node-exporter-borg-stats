#!/usr/bin/env python3
# coding: utf-8
import subprocess
import re
import os
import sys
import time
import shutil
from datetime import datetime
from optparse import OptionParser

textfile_collector_dir="/var/lib/prometheus/node-exporter"

optp = OptionParser()
optp.add_option('-r', '--repository', help='Required: Repository to check', dest='repository')
optp.add_option('-k', '--key', help='Required: Repository passkey', dest='repokey')
optp.add_option('-m', '--metric',help='Required: Unique metric name',dest='metric')
optp.add_option('-n', '--hostname',help='Required: Hostname where repository is located', dest='hostname')

optp.add_option('-i', '--sshargs', help='Optional: Additional arguments to pass to SSH command',dest='sshargs')
optp.add_option('-v', '--verbose',help="Print output to terminal", action='store_true',dest='verbose')
optp.add_option('-q', '--quiet',help="Run in silent mode", action='store_true',dest='quiet')

opts, args = optp.parse_args()

if opts.repository is None:
	sys.exit('Repository must be specified')
repository = opts.repository

if opts.repokey is None:
	sys.exit('Repokey must be specified')
repokey = opts.repokey
os.environ["BORG_PASSPHRASE"] = repokey

if opts.metric is None:
	sys.exit('Unique metric name must be specified')
metric = opts.metric

if opts.sshargs is not None:
	os.environ["BORG_RSH"] = opts.sshargs

if opts.hostname is None:
	sys.exit('Hostname required')
hostname = opts.hostname

if not os.path.exists(textfile_collector_dir):
	sys.exit("Error: Textfile directory does not exist")



''' 
Verbosity config
0 = Quiet. All messages including errors suppressed.
1 = Normal mode. Errors shown.
2 = Verbose. Everything printed. 
'''

if opts.verbose is True and opts.quiet is True:
	sys.exit("Error: Conflicting arguments --quiet and --verbose")
elif opts.verbose is True and opts.quiet is not True:
	verbosity = 2
elif opts.verbose is not True and opts.quiet is True:
	verbosity = 0
else:
	verbosity = 1

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

if verbosity >= 1:
	print("Updating Prometheus for Borg Repository " + repository)

tmp_file_name = textfile_collector_dir+"/"+metric+".tmp"
prom_file_name = textfile_collector_dir+"/"+metric+".prom"

cmd_borg_list=["borg","list", repository]
proc_borg_list = subprocess.Popen(cmd_borg_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
proc_borg_list.wait()


#Check for non-zero exit codes on borg list command
if proc_borg_list.returncode != 0:
	#Only return errors if verbosity is 1 or 2
	if verbosity >= 1:
		for line in proc_borg_list.stderr.readlines():
			m = re.search("passphrase supplied .* is incorrect.", line)
			if m is not None:
				sys.exit("ERROR: Incorrect Borg repokey for repo {}".format(repository))
					

			m = re.search("Failed to create/acquire the lock", line)
			if m is not None:
				sys.exit("ERROR: Unable to obtain lock on repository")

			else:
				print(line)
	sys.exit();

archives = {}
count_archives = 0

#Loop through archives discovered in the 'borg list' command
for archive in proc_borg_list.stdout.readlines():
	if verbosity == 2:
		print(archive)

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

if verbosity >= 1:
	print("Repo " + repository +": " + str(len(archives))+" different archives")
	print("Repo " + repository +": " + str(count_archives)+" archives in total")

# Prepare temporary file
tmp_file = open(tmp_file_name,"w+")

for archive,value in archives.items():
	archive_name = value['name']
	archive_datetime=value['datetime']

	if verbosity == 2:
		print("Updating {} from archive {}".format(archive,archive_name))
	print_prom(tmp_file, hostname, archive, "borg_backup_last_update_"+metric, time.mktime(archive_datetime.timetuple()))
	print_prom(tmp_file, hostname, archive, "borg_backup_age_"+metric, time.time() - time.mktime(archive_datetime.timetuple()))

	#Execute borg info command
	cmd_borg_info=["borg","info",repository+"::"+archive_name]
	proc_borg_info = subprocess.Popen(cmd_borg_info, stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
	proc_borg_info.wait()	

	#Quit without updating file if any errors occur while running borg info
	if proc_borg_info.returncode != 0:
		if verbosity >= 1:
			for line in proc_borg_list.stderr.readlines():
					m = re.search("Broken pipe", line)
					if m is not None:
							print("ERROR: Broken pipe while connecting to " + borg_repo)
							sys.exit();
					else:
							print(line)
							sys.exit();
		else:
			sys.exit()

for line in proc_borg_info.stdout.readlines():
	if verbosity == 2:
		print(line)
	m=re.search("Number of files: (?P<files_number>\d*)", line)
	if m:
		print_prom(tmp_file, hostname, archive, "borg_backup_files_"+metric, m.group('files_number'))

	m=re.search("Chunk index:\s*(?P<chunk_index_unique>\d*)\s*(?P<chunk_index_total>\d*)", line)
	if m:
		print_prom(tmp_file, hostname, archive, "borg_backup_chunks_unique_"+metric, m.group('chunk_index_unique'))
		print_prom(tmp_file, hostname, archive, "borg_backup_chunks_total_"+metric, m.group('chunk_index_total'))

	m=re.search("This archive:\s*(?P<original_size>\d*.\d*)\s(?P<original_size_unit>[A-Za-z]{2})\s*(?P<compressed_size>\d*.\d*)\s(?P<compressed_size_unit>[A-Za-z]{2})\s*(?P<total_size>\d*.\d*)\s(?P<total_size_unit>[A-Za-z]{2})", line)
	if m:
		print_prom(tmp_file, hostname, archive, "borg_backup_last_size_"+metric, calc_bytes(float(m.group('original_size')), m.group('original_size_unit')))
		print_prom(tmp_file, hostname, archive, "borg_backup_last_size_compressed_"+metric, calc_bytes(float(m.group('compressed_size')), m.group('compressed_size_unit')))
		print_prom(tmp_file, hostname, archive, "borg_backup_last_size_dedup_"+metric, calc_bytes(float(m.group('total_size')), m.group('total_size_unit')))

	m=re.search("All archives:\s*(?P<original_size>\d*.\d*)\s(?P<original_size_unit>[A-Za-z]{2})\s*(?P<compressed_size>\d*.\d*)\s(?P<compressed_size_unit>[A-Za-z]{2})\s*(?P<total_size>\d*.\d*)\s(?P<total_size_unit>[A-Za-z]{2})", line)
	if m:
		print_prom(tmp_file, hostname, archive, "borg_backup_total_size_"+metric, calc_bytes(float(m.group('original_size')), m.group('original_size_unit')))
		print_prom(tmp_file, hostname, archive, "borg_backup_total_size_compressed_"+metric, calc_bytes(float(m.group('compressed_size')), m.group('compressed_size_unit')))
		print_prom(tmp_file, hostname, archive, "borg_backup_total_size_dedup_"+metric, calc_bytes(float(m.group('total_size')), m.group('total_size_unit')))

if verbosity >= 1:
	print("Repo " + repository + ": Complete.")

tmp_file.close()
shutil.move(tmp_file_name, prom_file_name)