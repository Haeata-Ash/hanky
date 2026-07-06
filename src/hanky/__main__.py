import sys

from hanky import HankyPipeline
from hanky.errors import HankyError


def main():
    try:
        # default to basic model
        hanky = HankyPipeline("basic")
        hanky.run()
    except HankyError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
