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

    matrix-bot-api = with ps; buildPythonPackage rec {
      pname = "matrix_bot_api";
      version = "0.1";
      propagatedBuildInputs = [ matrix-client ];
      src = fetchFromGitHub {
        owner = "shawnanastasio";
        repo = "python-matrix-bot-api";
        rev = "962941c1ae7adec9330b4ce27e15482ac20ae1dd";
        sha256 = "18p1j7n1czp25qdzddz9b59br28akq05lg6ci711387bf58952r5";
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
    matrix-bot-api
    PyMVGLive
    feedparser
  ];

in buildEnv {
  name = "bernd-env";
  paths = [
    (python3.withPackages (ps: python-requirements ps))
  ];
}
