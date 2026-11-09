#!/bin/sh
# Run by the human submitter. Adds YOUR Signed-off-by and sends via b4.
#   setup               create the signing key, register with the web endpoint
#   verify <challenge>  finish registration with the code from the email
#   <series>            sign and send: wcd934x-mclk msm-va-align sm8150-camera nura-sensors
tree() { [ "$1" = nura-sensors ] && echo /work/libcamera || echo /work/next; }
case "$1" in
setup)
	cd /work/next; git checkout -q b4/msm-va-align
	patatt genkey -n default
	git config --global patatt.signingkey ed25519:default
	git config --global patatt.selector default
	b4 send --web-auth-new
	echo "Check gauravsuman007@gmail.com, then run: verify <challenge>" ;;
verify)
	cd /work/next; b4 send --web-auth-verify "$2" ;;
wcd934x-mclk|msm-va-align|sm8150-camera|nura-sensors)
	cd "$(tree "$1")"; git checkout -q "b4/$1" || exit 1
	r=$(b4 prep --show-info | sed -n 's/^series-range: //p'); cover=${r%%..*}
	git log --reverse --format='  %h %s' "$cover..HEAD"
	echo; echo "Adding Signed-off-by means you certify the Developer's Certificate"
	echo "of Origin (Documentation/process/submitting-patches.rst) for these."
	printf 'Type "I certify" to sign: '; read a; [ "$a" = "I certify" ] || exit 1
	git log --format=%B "$cover..HEAD" | grep -q '^Signed-off-by: Gaurav' ||
		git rebase -q --exec 'git commit -q --amend --no-edit -s' "$cover" || exit 1
	b4 prep --check; b4 send ;;
*) sed -n 2,6p "$0" ;;
esac
