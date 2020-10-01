# Princeton Geniza Project - search prototype

![tests](https://github.com/Princeton-CDH/geniza/workflows/tests/badge.svg?branch=experiment%2Fsearch)

## Development instructions

Initial setup and installation:

- **recommended:** create and activate a python 3.x virtual environment, perhaps with ``virtualenv`` or ``venv``

- Use pip to install required python dependencies:
```
pip install -r requirements.txt
```

Create a new solr core in your development solr instance using the 
distributed solr configuration files for this project:
```
solr create -c geniza -d solr_conf
```

Copy `local_settings.cfg.sample` to `local_settings.cfg` and configure
as appropriate for your environment.

Set required Flask environment variables.

In Bash:
```bash
export FLASK_APP=scripts/server.py FLASK_ENV=development
```

In Csh:
```csh
setenv FLASK_APP scripts/server.py 
setenv FLASK_ENV=development
```

To index data in Solr, run the index Flask command with the path
to the CSV file you'd like to index.
```
flask index data/pgp-metadata.csv
```

To run the Flask server:
```
flask run 
```
