# Basis-Image mit Conda-Unterstützung
FROM continuumio/miniconda3:latest AS conda-stage

# Setze Arbeitsverzeichnis
WORKDIR /app

# Kopiere nur die environment.yml
COPY environment.yml /app/environment.yml

# Installiere Abhängigkeiten mit Conda
RUN conda env create -f /app/environment.yml && \
    conda clean -afy

# Setze den PATH für die Conda-Umgebung
ENV PATH=/opt/conda/envs/audio_mining/bin:$PATH

# Zweite Stage: Finales Image
FROM continuumio/miniconda3:latest

# Setze Arbeitsverzeichnis
WORKDIR /app

# Kopiere die Conda-Umgebung aus der ersten Stage
COPY --from=conda-stage /opt/conda /opt/conda

# Setze den PATH für die Conda-Umgebung
ENV PATH=/opt/conda/envs/audio_mining/bin:$PATH

# Kopiere Projektdateien
COPY . /app

# Installiere das Projekt in der aktiven Conda-Umgebung
RUN conda run -n audio_mining pip install .

# Installiere jq für JSON-Verarbeitung
RUN apt-get update && apt-get install -y jq && apt-get clean

# Kopiere das PID-Management-Skript und mache es ausführbar
RUN chmod +x /app/manage_audio_miner.sh

# Aktivieren der Conda-Umgebung beim Start
SHELL ["/bin/bash", "-c"]
RUN echo "source activate audio_mining" >> ~/.bashrc

# Setze das Skript als ENTRYPOINT
ENTRYPOINT ["/bin/bash", "/app/manage_audio_miner.sh", "start"]