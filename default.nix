with import <nixpkgs> {};

let

  python-requirements = ps: with ps; let

    PyMVGLive = with ps; buildPythonPackage rec {
      pname = "PyMVGLive";
      version = "1.1.4";
      propagatedBuildInputs = [ requests ];
      src = fetchPypi {
        inherit pname version;
        sha256 = "0c81dc7e306501cd63d88ab57dedf277bf6b778085d1bceeef38d5484eed046a";
      };
      doCheck = false;
    };

    matrix-nio = with ps; buildPythonPackage rec {
      pname = "matrix-nio";
      version = "0.9.0";
      propagatedBuildInputs = [
        attrs
        future
        aiohttp
        aiofiles
        h11
        h2
        Logbook
        jsonschema
        unpaddedbase64
        pycryptodome
        atomicwrites
        python-olm
        peewee
        cachetools
      ];
      src = fetchPypi {
        inherit pname version;
        sha256 = "5986df619b56803546cb969b436ae87f8d207a359f3597f3d8e4e2d86946dc53";
      };
    };

  in [
    matrix-nio
    PyMVGLive
    feedparser
  ];

in buildEnv {
  name = "cyberbot-env";
  paths = [
    (python3.withPackages (ps: python-requirements ps))
  ];
}
