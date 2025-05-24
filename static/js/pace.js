document.addEventListener('DOMContentLoaded', () => {
    const workoutDateInput = document.getElementById('workoutDate');
    const workoutTimeInput = document.getElementById('workoutTime');
    const workoutDistanceInput = document.getElementById('workoutDistance');
	const calculatedPaceInput = document.getElementById('calculatedPace');

    // --- Auto-populate Date ---
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const day = String(today.getDate()).padStart(2, '0');
    workoutDateInput.value = `${year}-${month}-${day}`;

    // --- Pace Calculation Logic ---

    // Converts H:M:S.ms string to total seconds
    function parseTimeStringToSeconds(timeStr) {
        if (!timeStr) return 0;
        const parts = timeStr.split(':');
        let totalSeconds = 0;

        if (parts.length === 3) { // HH:MM:SS.ms
            const hours = parseInt(parts[0]);
            const minutes = parseInt(parts[1]);
            const secondsMs = parseFloat(parts[2]);
            totalSeconds = hours * 3600 + minutes * 60 + secondsMs;
        } else if (parts.length === 2) { // MM:SS.ms
            const minutes = parseInt(parts[0]);
            const secondsMs = parseFloat(parts[1]);
            totalSeconds = minutes * 60 + secondsMs;
        } else if (parts.length === 1) { // SS.ms (less common for workouts but for robustness)
            totalSeconds = parseFloat(parts[0]);
        }
        return totalSeconds;
    }

    // Formats total seconds into MM:SS.ms
    function formatSecondsToHMS(totalSeconds) {
        if (isNaN(totalSeconds) || totalSeconds < 0) return '--:--.--';

        const minutes = Math.floor(totalSeconds / 60);
        const remainingSeconds = totalSeconds % 60;

        const seconds = Math.floor(remainingSeconds);
        const milliseconds = Math.round((remainingSeconds - seconds) * 100); // Get 2 digits for ms

        const formattedMinutes = String(minutes).padStart(2, '0');
        const formattedSeconds = String(seconds).padStart(2, '0');
        const formattedMilliseconds = String(milliseconds).padStart(2, '0');

        return `${formattedMinutes}:${formattedSeconds}.${formattedMilliseconds}`;
    }

    function calculatePace() {
        const timeStr = workoutTimeInput.value;
        const distanceMeters = parseFloat(workoutDistanceInput.value);

        if (timeStr && distanceMeters > 0) {
            const totalSeconds = parseTimeStringToSeconds(timeStr);
            if (isNaN(totalSeconds) || totalSeconds <= 0) {
				calculatedPaceInput.value = 'Invalid Time';
				return;
			}

			// Pace is time per 500m
			const paceSecondsPer500m = (totalSeconds / distanceMeters) * 500;
			calculatedPaceInput.value = formatSecondsToHMS(paceSecondsPer500m);
		} else {
			calculatedPaceInput.value = '--:--.--';
		}
    }

    // Event listeners to update pace on input change
    workoutTimeInput.addEventListener('input', calculatePace);
    workoutDistanceInput.addEventListener('input', calculatePace);

    // Initial calculation on load (if fields have default values or are pre-filled)
    calculatePace();
});