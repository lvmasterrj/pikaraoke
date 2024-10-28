from subprocess import check_output

# Caminho completo para o Python 3.11
python_path = '/usr/local/bin/python3.11'

jj = (check_output(["yt-dlp", "--version"]).strip().decode("utf8"))

print(jj)