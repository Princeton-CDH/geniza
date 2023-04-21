#!/bin/bash

# script for counting the number of transcriptions and uinque pgpids
# over time in the pgp-text git repository. 
# Generates a csv file of counts per date.
# To run, check out a local copy of the pgp-text repo,
# and run this bash command in the base directory of that repo

# NOTE: regexes will need revising when translations are added


# adapted from https://blog.benoitblanchon.fr/git-file-count-vs-time/

OUTPUT=transcription_stats.csv

# create output file with a CSV header
echo "date;transcription files;documents" > $OUTPUT

# function that counts files matching the specified regex
count() {
    git ls-tree -r --name-only $COMMIT | grep $1 | wc -l | sed 's/ //g'
}

count_pgpids() {
	git ls-tree -r --name-only $COMMIT | grep $1 | sed -E 's/(^.*PGPID)// ' | sed -E 's/_.*$//' | uniq | wc -l | sed 's/ //g'
}
   
# for each commit in log
git log --pretty="%H %cd" --date=short | while read COMMIT DATE
do
    # skip commits made on the same day
    [ "$PREV_DATE" == "$DATE" ] && continue
    PREV_DATE="$DATE"

    # count files
    TXT_FILES=$(count ".*\.txt$")
    # count unique pgpids
    DOCS=$(count_pgpids "PGPID")

    # print to console
    echo $DATE
    echo " $TXT_FILES	transcriptions"
    echo " $DOCS documents"

    # append to CSV file
    echo "$DATE,$TXT_FILES,$DOCS" >> $OUTPUT 
done