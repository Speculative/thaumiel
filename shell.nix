with import <nixpkgs> {}; {
  pyEnv = stdenv.mkDerivation {
    name = "py";
    buildInputs = [
    	stdenv
	python35
	python35Packages.beautifulsoup4
	python35Packages.pep8
	];
  };
}
