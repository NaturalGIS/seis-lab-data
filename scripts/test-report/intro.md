## Introduction

<!-- Placeholder text: replace with the final introduction before delivering the report. -->

This document reports the results of the automated tests of Seis-Lab-Data, the
catalog of marine survey data. The tests are executed automatically for every
release of the software, on the same version of the code that is delivered.

The normal test results can always be consulted by looking at the GitHub Actions logs
page, under <https://github.com/NaturalGIS/seis-lab-data/actions>

The tests are of three kinds:

- **Unit tests** check individual parts of the software in isolation, such as the
  reading of metadata from survey files or the validation of user input.
- **Integration tests** check that the parts of the software work together with
  its database, exercising the operations of the catalog as they are performed in
  production.
- **End-to-end tests** operate the web application through a real web browser, as
  a user would, logging in and creating, editing and publishing catalog entries.

The rest of this report lists every test, grouped by area of functionality. Each
entry describes the behaviour being verified and the result of its verification.
