"""Optional offline calculator: needs --input; never obtains hotel rates itself."""
from src.hotel_estimate import main

if __name__ == "__main__":
    raise SystemExit(main())
