# node-exporter-borg-stats
Export stats on BorgBackup repositories to a file to be scraped by node-exporter's textfile collector

A slightly adapted version of https://framagit.org/tigre-bleu/prometheus-borg-exporter by Tigre-Bleu

# Usage
Call as part of a cron job, or borgmatic post-backup hook. 

**Metrics Collected**

Metric name | Description
------------|------------
borg_backup_last_update_            | POSIX timestamp of last archive
borg_backup_age_                    | Age in seconds of last archive (current time - POSIX timestamp)
borg_backup_files_                  | Number of files in repository
borg_backup_last_size_              | Size of last archive (bytes)
borg_backup_last_size_compressed_   | Compressed size of last archive (bytes)          
borg_backup_last_size_dedup_        | Deduplicated size of last archive (bytes)
borg_backup_total_size_             | Total repository size (bytes)
borg_backup_total_size_compressed_  | Compressed size of repository (bytes)
borg_backup_total_size_dedup_       | Deduplicated size of repository (bytes)
borg_backup_chunks_unique_          | Unique chunks in repository
borg_backup_chunks_total_           | Total chunks in repository


The above table shows the prefix of the metrics collected. The full metric name is the prefix, with the metric flag (specified with `-m` or `--metric`) appended.

Below is an example `.prom` file:

```
borg_backup_last_update_local_repo{host="borghost01", archive="foobarArchive"} 1583307343.0
borg_backup_age_local_repo{host="borghost01", archive="foobarArchive"} 31439.658803
borg_backup_files_local_repo{host="borghost01", archive="foobarArchive"} 1408069
borg_backup_last_size_local_repo{host="borghost01", archive="foobarArchive"} 5.43158744121e+12
borg_backup_last_size_compressed_local_repo{host="borghost01", archive="foobarArchive"} 5.24467046449e+12
borg_backup_last_size_dedup_local_repo{host="borghost01", archive="foobarArchive"} 1013763276.8
borg_backup_total_size_local_repo{host="borghost01", archive="foobarArchive"} 2.17142551369e+14
borg_backup_total_size_compressed_local_repo{host="borghost01", archive="foobarArchive"} 2.09852789277e+14
borg_backup_total_size_dedup_local_repo{host="borghost01", archive="foobarArchive"} 4.02421255766e+12
borg_backup_chunks_unique_local_repo{host="borghost01", archive="foobarArchive"} 2496875
borg_backup_chunks_total_local_repo{host="borghost01", archive="foobarArchive"} 126809913
```


# Examples
**Check local repository**

`$ node-exporter-borg-stats.py --repository /mnt/data/foo --key FooBarKey --metric local_repo --hostname borghost01`

**Check remote archive over SSH, with arguments**

`$ node-exporter-borg-stats.py --repository borg-user@borghost02:/mnt/data/borg-inbound/foo --key FooBarKey --metric remote_repo --sshargs 'ssh -i /home/borg-user/privkey' --hostname borghost02`
