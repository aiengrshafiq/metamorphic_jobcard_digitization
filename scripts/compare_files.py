import os

# Paths to the two folders
folder1 = r"C:\projects\metamorphic_jobcard_digitization\alembic\versions"
folder2 = r"C:\Backup\Projects\Metamorphic Jobcard Digitization\initial 49 - V3 - not working\alembic\versions"

# Get list of file names in each folder
files1 = set(os.listdir(folder1))
files2 = set(os.listdir(folder2))

# Find files only in folder1
only_in_folder1 = files1 - files2

# Find files only in folder2
only_in_folder2 = files2 - files1

# Print results
print("Files only in Folder 1:")
for f in sorted(only_in_folder1):
    print(f)

print("\nFiles only in Folder 2:")
for f in sorted(only_in_folder2):
    print(f)

# Optional: files present in both folders
common_files = files1 & files2
print(f"\nFiles in both folders ({len(common_files)}):")
for f in sorted(common_files):
    print(f)
