#!/bin/bash

# Array to store process IDs of started audio_miner instances
pids=()

# Function to start audio_miner processes based on JSON input
start() {
  json_data="$2"
  
  # Check if JSON data is provided
  if [[ -z "$json_data" ]]; then
    echo "No JSON data provided."
    exit 1
  fi

  # Validate the JSON format
  echo "$json_data" | jq . > /dev/null 2>&1
  if [[ $? -ne 0 ]]; then
    echo "Invalid JSON format. $json_data"
    exit 1
  fi

  # Parse the JSON and start audio_miner processes for each entry
  echo "$json_data" | jq -c '.[]' | while IFS= read -r line; do
    # Extract arguments and sender information from JSON
    args=$(echo "$line" | jq -r '.args')
    sender=$(echo "$line" | jq -r '.args' | grep -oP '(?<=--sender )\S+')
    sender=${sender:-unknown} # Default to "unknown" if sender is not specified

    # Start the audio_miner process and log its output
    echo "Starting audio_miner for sender: $sender"
    nohup audio_miner $args > /app/logs/audio_miner_${sender}_$(date +%Y%m%d%H%M%S).log 2>&1 &
    pids+=($!) # Store the process ID
  done

  # Save all process IDs to a file for later management
  echo "${pids[@]}" > /app/audio_miner_pids.txt
}

# Function to stop all running audio_miner processes
stop() {
  # Check if the PID file exists
  if [ -f /app/audio_miner_pids.txt ]; then
    # Iterate through each PID and attempt to terminate the process
    for pid in $(cat /app/audio_miner_pids.txt); do
      kill $pid 2>/dev/null || echo "Process $pid already stopped."
    done
    # Remove the PID file after stopping all processes
    rm /app/audio_miner_pids.txt
  else
    echo "No running processes found."
  fi
}

# Function to check the status of running audio_miner processes
status() {
  # Check if the PID file exists
  if [ -f /app/audio_miner_pids.txt ]; then
    # Iterate through each PID and check if the process is still running
    for pid in $(cat /app/audio_miner_pids.txt); do
      if ps -p $pid > /dev/null 2>&1; then
        echo "Process $pid is running."
      else
        echo "Process $pid is not running."
      fi
    done
  else
    echo "No running processes found."
  fi
}

# Main script logic to handle start, stop, and status commands
case "$1" in
  start)
    shift
    start "$@"
    ;;
  stop)
    stop
    ;;
  status)
    status
    ;;
  *)
    # Display usage instructions if an invalid command is provided
    echo "Usage: $0 {start <json_data> | stop | status}"
    exit 1
    ;;
esac

# If the start command is used, keep the script running
if [[ "$1" == "start" ]]; then
  echo "audio_miner-Dienst läuft. Drücke Strg+C, um den Container zu stoppen."
  tail -f /dev/null
fi