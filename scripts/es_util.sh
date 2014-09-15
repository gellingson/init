MKREPO='{
    "type": "fs",
    "settings": {
        "location": "/tmp/esbackups/sept15carbyr",
        "compress": true
    }
}'

#curl -XGET 'http://localhost:9200/_snapshot/_all'
#curl -XPUT 'http://localhost:9200/_snapshot/carbyr_backup' -d "$MKREPO"
#curl -XGET 'http://localhost:9200/_snapshot/carbyr_backup?pretty'
#curl -XPUT "localhost:9200/_snapshot/carbyr_backup/snapshot_1?wait_for_completion=true"
#curl -XGET "localhost:9200/_snapshot/carbyr_backup/snapshot_1"
#curl -XPOST "localhost:9200/_snapshot/carbyr_backup/snapshot_1/_restore"

