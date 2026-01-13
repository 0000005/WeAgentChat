import csv
import re
import os

def parse_markdown_to_csv(md_file_path, csv_file_path):
    with open(md_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = []
    # Header for CSV
    # category, tags, name, description
    
    for line in lines:
        line = line.strip()
        # Look for table rows: | Category | Tags | Name | Intro |
        if line.startswith('|') and not line.startswith('| :---'):
            parts = [p.strip() for p in line.split('|')]
            # Markdown tables split by '|' result in empty first and last elements if the line starts/ends with '|'
            # Row structure: ['', 'Category', 'Tags', 'Name', 'Intro', '']
            if len(parts) >= 5:
                category = parts[1].replace('**', '')
                tags = parts[2]
                name = parts[3]
                description = parts[4]
                
                # Skip the table header row
                if name == "人物姓名" or category == "分类":
                    continue
                
                if name and category:
                    data.append({
                        "category": category,
                        "tags": tags,
                        "name": name,
                        "description": description
                    })

    with open(csv_file_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["category", "tags", "name", "description"])
        writer.writeheader()
        writer.writerows(data)

    print(f"Successfully converted {len(data)} personas to {csv_file_path}")

if __name__ == "__main__":
    md_path = r"e:\workspace\code\DouDouChat\dev-docs\temp\preset_friends_list.md"
    csv_path = r"e:\workspace\code\DouDouChat\dev-docs\temp\preset_friends_list.csv"
    parse_markdown_to_csv(md_path, csv_path)
