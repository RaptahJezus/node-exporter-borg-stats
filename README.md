# node-exporter-borg-stats
Export stats on BorgBackup repositories to a file to be scraped by node-exporter's textfile collector

A slightly adapted version of https://framagit.org/tigre-bleu/prometheus-borg-exporter by Tigre-Bleu

# Usage
Call as part of a cron job, or borgmatic post-backup hook. 

# Examples
**Check local repository**

`$ node-exporter-borg-stats.py --repository /mnt/data/foo --key FooBarKey --metric local_repo --hostname borghost01`

Would produce the following file
```
```
