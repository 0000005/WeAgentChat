import argparse
import os
import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="DouDouChat backend runner")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--data-dir", dest="data_dir", default=os.getenv("DOUDOUCHAT_DATA_DIR"))
    args = parser.parse_args()

    if args.data_dir:
        os.environ["DOUDOUCHAT_DATA_DIR"] = args.data_dir

    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
