# Contributor's License Agreement #

Sign the [CLA](https://cla.developers.google.com/about/google-individual).

# Installing `git-rv` #

  1. Follow the `README.md` instructions for [git-rv](https://github.com/GoogleCloudPlatform/git-rv), which roughly boil down to:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/git-rv
    export PATH=$PATH:/path/to/git-rv-directory
    ```

  1. Confirm that `git-rv` is on your path

    ```bash
    which git-rv
    ```

  1. Confirm that `git` sees the `git-rv` executable

    ```bash
    # Notice: no dash between `git` and `rv`
    git rv
    ```

# Submitting patches #

  1. [Checkout the cloud-playground source](https://code.google.com/p/cloud-playground/)
  1. Hack, hack, hack
  1. Commit changes to your local git repo
  1. Follow the `README.md` instructions for [git-rv](https://github.com/GoogleCloudPlatform/git-rv) to submit your changes to review to one of the Cloud Playground committers, e.g.

    ```bash
    git rv export -r fredsa@google.com
    ```

  1. Once you have an `LGTM`, submit your changes

    ```bash
    git rv submit
    ```
