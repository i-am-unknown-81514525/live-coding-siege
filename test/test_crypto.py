from crypto.core import DeterRnd, Handler


def test() -> Handler[int]:
    return (1, lambda x: x)


def test2() -> Handler[bool]:
    return (1, lambda x: x == 0)


if __name__ == "__main__":
    rnd = DeterRnd(test(), test2()).with_seed(input("Seed: "))
    print(rnd.retrieve())
