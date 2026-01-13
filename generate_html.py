"""Generate HTML tables with sticky headers for Ruff rule analysis."""


def generate_html_table(df, title, filename):
    """Generate a standalone HTML file with a styled table and sticky header.

    Args:
        df: Polars DataFrame containing the rules data
        title: Page title
        filename: Output HTML filename
    """

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background-color: #fff;
        }}

        .nav {{
            padding: 10px 20px;
            border-bottom: 1px solid #e1e4e8;
            background-color: #f6f8fa;
        }}

        .nav a {{
            color: #0366d6;
            text-decoration: none;
            margin-right: 20px;
            font-size: 14px;
        }}

        .nav a:hover {{
            text-decoration: underline;
        }}

        .table-wrapper {{
            overflow-x: auto;
            overflow-y: auto;
            height: calc(100vh - 41px);
            max-width: 1400px;
            margin: 0 auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}

        thead {{
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: #f6f8fa;
        }}

        th {{
            padding: 8px 12px;
            text-align: left;
            font-weight: 600;
            color: #24292e;
            background-color: #f6f8fa;
            border-bottom: 1px solid #e1e4e8;
            white-space: nowrap;
            cursor: pointer;
            user-select: none;
        }}

        th:hover {{
            background-color: #e1e4e8;
        }}

        th.sortable::after {{
            content: ' ↕';
            opacity: 0.3;
        }}

        th.sorted-asc::after {{
            content: ' ↑';
            opacity: 1;
        }}

        th.sorted-desc::after {{
            content: ' ↓';
            opacity: 1;
        }}

        td {{
            padding: 8px 12px;
            border-bottom: 1px solid #f0f0f0;
        }}

        tbody tr:hover {{
            background-color: #f6f8fa;
        }}

        .category-correctness {{
            background-color: #ff9aa9;
        }}

        .category-suspicious {{
            background-color: #ffc66a;
        }}

        .category-complexity {{
            background-color: #c7ff8a;
        }}

        .category-perf {{
            background-color: #8aff8a;
        }}

        .category-style {{
            background-color: #fff58a;
        }}

        .category-pedantic {{
            background-color: #8ac7ff;
        }}

        .category-restriction {{
            background-color: #c78aff;
        }}

        td a {{
            color: #0366d6;
            text-decoration: none;
        }}

        td a:hover {{
            text-decoration: underline;
        }}

        .code {{
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 12px;
        }}

        .rule-code {{
            font-weight: 600;
            color: #0366d6;
        }}
    </style>
</head>
<body>
    <nav class="nav">
        <a href="index.html">Home</a>
        <a href="on_by_default.html">Default Rules</a>
        <a href="off_by_default.html">Off-by-Default Rules</a>
    </nav>

    <div class="table-wrapper">
        <table id="rulesTable">
"""

    # Add table headers
    html_template += "            <thead>\n                <tr>\n"
    for col in df.columns:
        display_name = col.replace("_", " ").title()
        html_template += f'                    <th class="sortable" data-column="{col}">{display_name}</th>\n'
    html_template += "                </tr>\n            </thead>\n"

    # Add table body
    html_template += "            <tbody>\n"
    for row in df.iter_rows(named=True):
        html_template += "                <tr>\n"
        for col in df.columns:
            value = row[col]
            # Add category class to category cells
            cell_class = ""
            if col == "category" and value:
                cell_class = f' class="category-{value.lower()}"'

            if col == "rule":
                # Rule code with link
                rule_url = f"https://docs.astral.sh/ruff/rules/{value}"
                html_template += f'                    <td{cell_class}><a href="{rule_url}" target="_blank" class="code rule-code">{value}</a></td>\n'
            elif col == "name":
                # Name is already a slug, make it readable and add link
                rule_code = row.get("rule", "")
                if rule_code:
                    rule_url = f"https://docs.astral.sh/ruff/rules/{rule_code}"
                    html_template += f'                    <td{cell_class}><a href="{rule_url}" target="_blank">{value}</a></td>\n'
                else:
                    html_template += f"                    <td{cell_class}>{value}</td>\n"
            elif value is None:
                html_template += f"                    <td{cell_class}></td>\n"
            elif isinstance(value, (int, float)):
                html_template += f"                    <td{cell_class}>{value}</td>\n"
            else:
                html_template += f"                    <td{cell_class}>{value}</td>\n"
        html_template += "                </tr>\n"
    html_template += "            </tbody>\n"

    html_template += """        </table>
    </div>

    <script>
        // Sorting functionality
        const table = document.getElementById('rulesTable');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const headers = table.querySelectorAll('th.sortable');
        let sortState = {};

        headers.forEach((header, index) => {
            header.addEventListener('click', function() {
                const column = this.getAttribute('data-column');
                const columnIndex = index;

                // Toggle sort direction
                if (sortState.column === column) {
                    sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    sortState.column = column;
                    sortState.direction = 'asc';
                }

                // Update header classes
                headers.forEach(h => {
                    h.classList.remove('sorted-asc', 'sorted-desc');
                });
                this.classList.add(sortState.direction === 'asc' ? 'sorted-asc' : 'sorted-desc');

                // Sort rows
                const sortedRows = rows.sort((a, b) => {
                    const aCell = a.cells[columnIndex].textContent.trim();
                    const bCell = b.cells[columnIndex].textContent.trim();

                    // Try to parse as number
                    const aNum = parseFloat(aCell);
                    const bNum = parseFloat(bCell);

                    if (!isNaN(aNum) && !isNaN(bNum)) {
                        return sortState.direction === 'asc' ? aNum - bNum : bNum - aNum;
                    }

                    // String comparison
                    if (sortState.direction === 'asc') {
                        return aCell.localeCompare(bCell);
                    } else {
                        return bCell.localeCompare(aCell);
                    }
                });

                // Re-append rows
                sortedRows.forEach(row => tbody.appendChild(row));
            });
        });
    </script>
</body>
</html>"""

    with open(filename, "w") as f:
        f.write(html_template)

    print(f"Generated {filename}")


def generate_index_page():
    """Generate an index page linking to both rule tables."""

    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ruff Rules Analysis</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background-color: #fff;
        }

        .nav {
            padding: 10px 20px;
            border-bottom: 1px solid #e1e4e8;
            background-color: #f6f8fa;
        }

        .nav a {
            color: #0366d6;
            text-decoration: none;
            margin-right: 20px;
            font-size: 14px;
        }

        .nav a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <nav class="nav">
        <a href="index.html">Home</a>
        <a href="on_by_default.html">Default Rules</a>
        <a href="off_by_default.html">Off-by-Default Rules</a>
    </nav>
</body>
</html>"""

    with open("docs/index.html", "w") as f:
        f.write(html)

    print("Generated index.html")
