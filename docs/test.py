import wrapt


def foo():
	print("FOO")
	return {"a": 1, "b": 2}



class FunctionProxy(wrapt.ObjectProxy):


	def __init__(self, *args, **kargs):
		super().__init__(*args, **kargs)
		print(args, kargs)
		return None


p = FunctionProxy(foo)
print(p)
