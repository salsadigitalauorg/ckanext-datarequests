#!/usr/bin/env sh
##
# Initialise CKAN data for testing.
#
set -e

. ${APP_DIR}/scripts/activate
CLICK_ARGS="--yes" ckan_cli db clean
ckan_cli db init
ckan_cli db upgrade

# Add data request tables
ckan_cli datarequests init-db
ckan_cli datarequests update-db

# Create some base test data
. $APP_DIR/scripts/create-test-data.sh
