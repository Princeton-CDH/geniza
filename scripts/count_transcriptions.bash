#!/bin/bash
## Usage: bash count_transcriptions.bash [options] 
##
## Expects to be run in a local copy of a the git repository 
## for PGP transcriptions.
##
## Options:
##   -h, --help    Display this message.
##   -q            Quiet mode; don't output totals to console
##

usage() {
  [ "$*" ] && echo "$0: $*"
  sed -n '/^##/,/^$/s/^## \{0,1\}//p' "$0"
  exit 2
} 2>/dev/null


# script for counting the number of transcriptions and uinque pgpids
# over time in the pgp-text git repository. 
# Generates a csv file of counts per date.
# To run, check out a local copy of the pgp-text repo,
# and run this bash command in the base directory of that repo

# NOTE: regexes will need revising when translations are added


# adapted from https://blog.benoitblanchon.fr/git-file-count-vs-time/

OUTPUT=transcription_stats.csv

# while getopts u:a:f: flag
# do
#     case "${flag}" in
#         q) quiet=${OPTARG};;
#     esac
# done

# Quiet option; false by default
OPT_QUIET=0

# Process all options supplied on the command line 
while getopts hqo:D: flag
do
    case "$flag" in
    (h) usage; exit 0;;
    (q) OPT_QUIET=1;;
    (o) out="$OPTARG";;
    (*) usage;;
    esac
done

# create output file with a CSV header
echo "date;transcription_count;transcribed_document_count" > $OUTPUT

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
    [ "$PREV_DATE" = "$DATE" ] && continue
    PREV_DATE="$DATE"

    # count transcription files
    TXT_FILES=$(count ".*\_transcription.txt$")
    # count unique pgpids for transcriptions
    DOCS=$(count_pgpids "PGPID.*transcription.txt$")

    # print to console unless quiet mode
    [ $OPT_QUIET == 1 ] || {
        echo $DATE
        echo " $TXT_FILES	transcriptions"
        echo " $DOCS documents"
    }

    # append to CSV file
    echo "$DATE,$TXT_FILES,$DOCS" >> $OUTPUT 
done