"""ft-023: PyInstaller hook for torch — belt-and-suspenders.

The main spec file already runs ``collect_all("torch")`` which folds in
hiddenimports/binaries/datas. This hook is a fallback for edge cases
where PyInstaller still drops dynamically-loaded submodules (CUDA
extension shims, ``torch._C`` private modules, ``torch.distributed``
backends, etc.) on certain machines.

Loaded automatically because the spec sets ``hookspath=["build/hooks"]``.
"""
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules

datas, binaries, hiddenimports = collect_all("torch")

# Pick up CUDA DLLs that ship inside torch's site-packages tree
# (torch/lib/*.dll, nvfuser, cublas, etc.).
binaries += collect_dynamic_libs("torch")

# Common subpackages that get dynamically imported via getattr / importlib.
hiddenimports += collect_submodules("torch._C")
hiddenimports += collect_submodules("torch.distributed")
hiddenimports += collect_submodules("torch.cuda")
hiddenimports += collect_submodules("torch.backends")
hiddenimports += [
    "torch._dynamo",
    "torch._inductor",
    "torch.jit",
    "torch.fx",
    "torch.utils.cpp_extension",
]
