#!/bin/bash
# Run this script using the Bash shell interpreter

# -----------------------------------------------------------------------------
# Auto Git Sync Script
# Continuously monitors a Git repository and automatically commits & pushes
# changes based on file change count or time interval.
# -----------------------------------------------------------------------------

function main() { # Define the main function that contains all script logic

	# ---------------- Configuration ----------------

	CHECK_INTERVAL_SECONDS=60      # Wait 60 seconds between each repository check
	MIN_WAIT_SECONDS=43200         # Force push at least every 43200 seconds (12 Hours)
	MIN_FILE_CHANGE_THRESHOLD=100  # Push early if 100+ files have changed

	last_push_epoch=$(date +%s) # Store current time in seconds since Unix epoch

	# ---------------- Monitoring Loop ----------------

	while true; do # Run indefinitely in a loop
		current_epoch=$(date +%s)                            # Get current time in epoch seconds
		elapsed_seconds=$((current_epoch - last_push_epoch)) # Time since last push

		# Remove all files over 100 MB
		find "zip/" -type f -size +100M -delete

		changed_files_count=$(git status --porcelain -uall | wc -l)
		# Get list of changed files from git and count them
		# --porcelain gives clean machine-readable output

		# ---------------- Status Output ----------------

		echo "------------------------------------------------------------" # Print separator line
		echo "Repository Status Report"                                     # Header title for clarity
		echo "Time                : $(date)"                                # Print current human-readable time
		echo "Changed Files       : ${changed_files_count}"                 # Show number of changed files
		echo "Time Since Last Push: ${elapsed_seconds} seconds"             # Show elapsed time since last push
		echo "------------------------------------------------------------" # Print separator line

		# ---------------- Trigger Conditions ----------------

		if [[ ${changed_files_count} -ge ${MIN_FILE_CHANGE_THRESHOLD} || ${elapsed_seconds} -ge ${MIN_WAIT_SECONDS} ]]; then
			# Check if we should push:
			# Condition 1: too many file changes
			# Condition 2: too much time has passed

			if [[ ${changed_files_count} -eq 0 ]]; then
				# If trigger happened but there are actually no changes

				echo "[INFO] Trigger reached but no changes detected. Resetting timer."
				# Inform user nothing needs to be done

				last_push_epoch=$current_epoch # Reset timer so we don't keep triggering

				sleep "${CHECK_INTERVAL_SECONDS}" # Wait before next check

				continue # Skip rest of loop and start next iteration
			fi        # End empty-change check

			# ---------------- Pull Latest Changes ----------------

			echo "[INFO] Pulling latest changes from remote repository..."
			# Inform user we are syncing with remote

			if ! git pull --rebase --autostash; then
				# Pull latest changes and reapply local changes on top
				# --rebase avoids merge commits
				# --autostash temporarily saves local changes

				echo "[ERROR] Failed to pull/rebase from remote repository." # Show error message
				echo "         Possible causes: merge conflicts, network issues, or auth failure."
				echo "         Action: Resolve manually and rerun script."

				sleep "${CHECK_INTERVAL_SECONDS}" # Wait before retrying

				continue # Skip rest of loop
			fi        # End git pull block

			# ---------------- Stage Changes ----------------

			echo "[INFO] Staging all changes (additions, modifications, deletions)..."
			# Explain staging step

			if ! git add -A; then
				# Stage all changes in repository

				echo "[ERROR] Failed to stage changes." # Error message
				echo "         Check file permissions or repository state."

				sleep "${CHECK_INTERVAL_SECONDS}" # Wait before retry

				continue # Skip loop iteration
			fi        # End git add block

			# ---------------- Commit Changes ----------------

			commit_timestamp=$(date -u +'%Y-%m-%d %H:%M:%S UTC')
			# Create a timestamp in UTC for commit message

			commit_message="Auto-sync commit (${commit_timestamp})"
			# Build readable commit message

			echo "[INFO] Creating commit..." # Inform commit step started

			if git commit -m "${commit_message}"; then
				# Try to commit staged changes

				echo "[SUCCESS] Commit created successfully." # Success message

			else
				# If commit fails (likely no changes)

				echo "[INFO] No new changes to commit (already up-to-date)." # Inform user

				sleep "${CHECK_INTERVAL_SECONDS}" # Wait before retry

				continue # Skip rest of loop
			fi        # End commit block

			# ---------------- Push Changes ----------------

			echo "[INFO] Pushing changes to remote repository..."
			# Inform user we are pushing

			if git push; then
				# Attempt to push committed changes to remote

				echo "[SUCCESS] Push completed successfully." # Success message

				last_push_epoch=$current_epoch
				# Reset timer after successful push

			else
				# If push fails

				echo "[ERROR] Failed to push changes to remote repository." # Error message
				echo "         Possible causes: authentication failure, protected branch, or network issues."
				echo "         Action: Verify credentials and repository permissions."
			fi # End git push block
		fi  # End trigger condition check

		# ---------------- Wait Before Next Check ----------------

		sleep "${CHECK_INTERVAL_SECONDS}"
		# Pause script before next loop iteration to avoid constant CPU usage

	done # End infinite loop
}     # End main function definition

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------

main # Call the main function to start execution
