{
  description = "llmwiki — Karpathy-style LLM wiki from your AI coding sessions";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        llmwiki = python.pkgs.buildPythonApplication {
          pname = "llmwiki";
          version = "0.9.0";
          format = "pyproject";

          src = ./.;

          nativeBuildInputs = [
            python.pkgs.setuptools
            python.pkgs.wheel
          ];

          propagatedBuildInputs = [
            python.pkgs.markdown
          ];

          # Unit tests run during the check phase.
          nativeCheckInputs = [
            python.pkgs.pytest
          ];

          checkPhase = ''
            runHook preCheck
            pytest tests/ -q --ignore=tests/e2e
            runHook postCheck
          '';

          meta = with pkgs.lib; {
            description = "LLM Wiki — Karpathy-style knowledge base from your AI coding sessions";
            homepage = "https://github.com/AlexanderMakarov/llm-wiki";
            license = licenses.mit;
            maintainers = [ ];
          };
        };
      in
      {
        packages.default = llmwiki;
        packages.llmwiki = llmwiki;

        devShells.default = pkgs.mkShell {
          packages = [
            python
            python.pkgs.markdown
            python.pkgs.pytest
            python.pkgs.ruff
          ];

          shellHook = ''
            echo "llmwiki dev shell — Python ${python.version}"
            echo "  pytest, ruff available"
          '';
        };
      }
    );
}
