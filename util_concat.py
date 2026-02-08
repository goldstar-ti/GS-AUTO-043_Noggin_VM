import os
import datetime

def prepare_python_for_notebooklm(source_folder, output_filename):
    """Combines python files into a single, formatted markdown file."""
    combined_content = "# Python Codebase\n\n"

    exclude_dirs = {"node_modules", ".git", ".venv", "__pycache__", ".scratch", ".scrap", ".repomix", ".venv_python312", "scratch"}    

    skipped_files = []
    combined_file_list = []
    
    for root, dirs, files in os.walk(source_folder):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith((".py", ".ini", ".txt", ".md", ".sql", ".json")):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    print(f"Processing file: {file_path} (size: {len(content)} char)\n")
                    # exclude node_modules and .git directories
                    if "node_modules" in file_path or ".git" in file_path or ".venv" in file_path:
                        print(f"Skipping file: {file_path} (excluded directory)\n")
                        skipped_files.append(file_path)
                        continue
                    combined_content += f"## FILE: {os.path.abspath(file_path)}\n```python\n{content}\n```\n\n"
                    combined_file_list.append(file_path)

    # Remove completely blank lines from the combined content
    # lines = combined_content.splitlines()
    # filtered_lines = [line for line in lines if line.strip() != ""]
    # combined_content = "\n".join(filtered_lines) + "\n"

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(combined_content)
    print(f"Prepared file saved as: {output_filename}")
    print("Skipped files:")
    for f in skipped_files:
        print(f"  {f}")
    print("Combined files:")
    for f in combined_file_list:
        print(f"  {f}")

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
source_folder = "./" 
output_filename = f"./.repomix/notebooklm_source_{timestamp}.md"
prepare_python_for_notebooklm(source_folder, output_filename)
