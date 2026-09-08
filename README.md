### Quantbit Customer360

it is customer 360

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app quantbit_customer360
```

After installation or migration, open `/customer360`. The route sends authenticated
Desk users to the Customer 360 page and preserves the optional customer query:

```text
/customer360?customer=CUST-0001
```

If no customer is supplied, the page opens a Customer selector. Access is limited
to Sales User, Sales Manager, and System Manager roles, and the API enforces the
current user's Customer read permission.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/quantbit_customer360
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
