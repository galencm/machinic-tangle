import argparse
import pathlib
import hashlib
import redis
from textx.metamodel import metamodel_from_file

def main():
    # add a pathling route
    # $ lings-path-add "/foo -> bar"

    parser = argparse.ArgumentParser()
    parser.add_argument("route", help="db host ip")
    parser.add_argument("--db-host",  default="127.0.0.1", help="db host ip")
    parser.add_argument("--db-port", type=int, default=6379, help="db port")
    args = parser.parse_args()

    db_settings = {"host" :  args.db_host, "port" : args.db_port}
    redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)
    routes_key = "machinic:routes:{}:{}".format(args.db_host, args.db_port)

    # pathling model
    pathling_model_file = pathlib.Path(pathlib.PurePath(pathlib.Path(__file__).parents[0], "pathling.tx"))
    pathling_metamodel = metamodel_from_file(pathling_model_file)
    route = args.route

    try:
        # validate
        path = pathling_metamodel.model_from_str(route)
        route_hash = hashlib.sha224(route.encode()).hexdigest()
        redis_conn.hmset(routes_key, {route_hash : route})
    except Exception as ex:
        print(ex)

