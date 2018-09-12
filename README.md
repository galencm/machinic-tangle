# machinic-tangle

## Installation

Pip:

```
pip3 install git+https://github.com/galencm/machinic-tangle --user --process-dependency-links
```

Develop while using pip:

```
git clone https://github.com/galencm/machinic-tangle
cd machinic-tangle/
pip3 install --editable ./ --user --process-dependency-links
```

Setup linting and formatting git commit hooks:

```
cd machinic-tangle/
pre-commit install
pre-commit install -t commit-msg
```

## Usage

**tangle-ui**

_overviews of connecting, routing and messaging_

```
tangle-ui  --size=1500x800 -- --db-port 6379 --db-host 127.0.0.1
```

Notes:

Because tangle-ui glues together functionality that involves wireless scanning and access point creation there is a sudo prompt in the terminal at startup when the subprocess calls are made.

APs are created with`create_ap`, not all wireless cards will work. An Alfa AWUS036NHA works.

**tangle-things**

_generate code for things hardware and software_

a button example using gsl, homie and platformio to generate and upload code onto a huzzah esp8266:

```
tangle-things button --model-type homie --name foo
cd button_foo/foo_button/
platformio run
platformio run -t upload
```

**A redis server must be accessible.**

To start one locally:

* Create a config file to enable keyspace events and snapshot.
* Run a redis-server process in the background

```
printf "notify-keyspace-events KEA\nSAVE 60 1\n" >> redis.conf
redis-server redis.conf --port 6379 &
```

The server can be stopped with the command:
```
redis-cli -p 6379 shutdown
```

## Contributing

[Contribution guidelines](CONTRIBUTING.md)

## License
Mozilla Public License, v. 2.0

[http://mozilla.org/MPL/2.0/](http://mozilla.org/MPL/2.0/)

