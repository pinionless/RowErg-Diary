// Wrap all your chart logic in a function that accepts the data
    function initializeSummaryChart( // Renamed from initializeYearlyChart
        chartElementId, // Added: ID of the chart container element
        categoriesData, // Renamed from yearsCategories
        metersSeriesData, 
        secondsSeriesData, 
        paceSeriesData, 
        repsSeriesData,
        xAxisTitle // New parameter for X-axis title
    ) {
        // Tooltip Formatters
        function formatMetersTooltip(val) {
            return val !== null ? val.toLocaleString() + " m" : null;
        }
        function formatDurationTooltip(totalSeconds) {
            if (totalSeconds === null || typeof totalSeconds === 'undefined' || totalSeconds < 0) return null;
            totalSeconds = parseFloat(totalSeconds);
            const h = Math.floor(totalSeconds / 3600);
            const m = Math.floor((totalSeconds % 3600) / 60);
            const s = Math.floor(totalSeconds % 60);
            return `${h}h ${m}m ${s}s`;
        }
        function formatPaceChartTooltip(total_split_seconds_raw) {
            if (total_split_seconds_raw === null || typeof total_split_seconds_raw === 'undefined' || total_split_seconds_raw <= 0) return null;
            total_split_seconds_raw = parseFloat(total_split_seconds_raw);
            const minutes = Math.floor(total_split_seconds_raw / 60);
            const remaining_seconds_float = total_split_seconds_raw % 60;
            const seconds_part = Math.floor(remaining_seconds_float);
            const milliseconds_decimal_part = Math.floor((remaining_seconds_float - seconds_part) * 10);
            return `${minutes}:${seconds_part.toString().padStart(2, '0')}.${milliseconds_decimal_part}`;
        }
        function formatRepsTooltip(val) {
            return val !== null ? val.toLocaleString() + " reps" : null;
        }

        // Helper function to set data label and X-axis label visibility
        function updateChartElementsVisibility(chartInstance, visibleItemCount) { // Renamed function
            const currentDataLabelEnabled = chartInstance.w.config.dataLabels.enabled;
            const currentXAxisLabelsShow = chartInstance.w.config.xaxis.labels.show; // Target labels.show

            let newDataLabelEnabled = currentDataLabelEnabled;
            let newXAxisLabelsShow = currentXAxisLabelsShow; // Target labels.show

            // Data labels logic
            if (visibleItemCount > 5) {
                if (currentDataLabelEnabled) newDataLabelEnabled = false;
            } else {
                if (!currentDataLabelEnabled) newDataLabelEnabled = true;
            }

            // X-axis labels logic
            if (visibleItemCount > 8) {
                if (currentXAxisLabelsShow) newXAxisLabelsShow = false; // Hide if currently shown
            } else {
                if (!currentXAxisLabelsShow) newXAxisLabelsShow = true; // Show if currently hidden
            }
            
            // Only update if there's a change to avoid unnecessary re-renders
            if (newDataLabelEnabled !== currentDataLabelEnabled || 
                newXAxisLabelsShow !== currentXAxisLabelsShow) { // Compare with labels.show
                chartInstance.updateOptions({
                    dataLabels: { enabled: newDataLabelEnabled },
                    xaxis: {
                        labels: { show: newXAxisLabelsShow } // Update labels.show
                    }
                }, false, false, false); // Pass false for redraw, animate, and updateSyncedCharts
            }
        }

        const commonXAxisOptions = {
            categories: [...categoriesData], // Use renamed parameter
            title: { text: xAxisTitle }, // Use new xAxisTitle parameter
            type: 'category',
            axisTicks: { show: true }, // Default state for ticks (remains as is)
            labels: { show: true } // Default state for labels
        };

        const baseChartSettings = {
            stroke: { show: true, width: 2, colors: ['transparent', 'transparent', 'transparent', 'transparent'] },
            dataLabels: { 
                enabled: true, // Default state, will be managed by events
                position: 'top',
                offsetY: -20,
                style: {
                    fontSize: '11px',
                    colors: ["#304758"]
                },
                formatter: function (val, opts) {
                    if (val === null) return '';
                    const seriesIndex = opts.seriesIndex;
                    if (seriesIndex === 0) { // Distance (m)
                        return Math.round(val).toLocaleString(); 
                    }
                    if (seriesIndex === 1) { // Duration (s)
                        const formatted = formatDurationTooltip(val);
                        return formatted !== null ? formatted : '';
                    }
                    if (seriesIndex === 2) { // Pace (s/500m)
                        const formatted = formatPaceChartTooltip(val);
                        return formatted !== null ? formatted : '';
                    }
                    if (seriesIndex === 3) { // Reps
                        return Math.round(val).toLocaleString();
                    }
                    return val; 
                }
            },
            xaxis: commonXAxisOptions,
            legend: { 
                onItemClick: {
                    toggleDataSeries: false 
                }
            },
            chart: { 
                height: 350, 
                zoom: { enabled: true },
                toolbar: { show: true },
                animations: {
                    enabled: true,
                    easing: 'easeinout',
                    speed: 800,
                    animateGradually: {
                        enabled: true,
                        delay: 150
                    },
                    dynamicAnimation: {
                        enabled: true,
                        speed: 350
                    }
                },
                events: {
                    legendClick: function(chartContext, seriesIndex, config) {
                        const clickedSeriesName = chartContext.w.globals.seriesNames[seriesIndex];
                        chartContext.w.globals.seriesNames.forEach((name) => {
                            if (name === clickedSeriesName) {
                                chartContext.showSeries(name);
                            } else {
                                chartContext.hideSeries(name);
                            }
                        });
                        // After handling series visibility, explicitly update the y-axes
                        // This is a workaround if y-axes don't update automatically based on visible series
                        // This might require more specific logic if ApexCharts doesn't auto-adjust axes correctly
                        // For now, assume ApexCharts handles y-axis updates based on visible series with seriesName matching.
                    },
                    mounted: function(chartContext, config) {
                        // For category axis, config.xaxis.categories.length gives total categories
                        // If initial min/max were set on xaxis, this would be different.
                        // Assuming full initial view here based on current chart_summary.js state.
                        const initialVisibleCount = chartContext.w.config.xaxis.categories.length;
                        updateChartElementsVisibility(chartContext, initialVisibleCount); // Use renamed function
                    },
                    zoomed: function(chartContext, { xaxis, yaxis }) {
                        // For category axes, minX and maxX in globals are category indices
                        const visibleCount = chartContext.w.globals.maxX - chartContext.w.globals.minX + 1;
                        updateChartElementsVisibility(chartContext, visibleCount); // Use renamed function
                    }
                }
            },
            plotOptions: {
                bar: {
                    horizontal: false, 
                    columnWidth: '75%',
                    dataLabels: {
                        position: 'top',
                    },
                }
            },
            colors: ['#008FFB', '#00E396', '#FEB019', '#FF4560']
        };

        // Ensure data arrays exist before trying to check their length
        const hasData = (metersSeriesData && metersSeriesData.length > 0) ||
                        (secondsSeriesData && secondsSeriesData.length > 0) ||
                        (paceSeriesData && paceSeriesData.length > 0) ||
                        (repsSeriesData && repsSeriesData.length > 0);

        // IMPORTANT: Select the chart element using the passed ID
        const chartContainer = document.querySelector("#" + chartElementId);

        if (!chartContainer) {
            console.error("Error: Chart container element with ID '" + chartElementId + "' not found in the DOM.");
            // Optionally, display a message in a fallback location or do nothing if the element is critical
            // For example, if you have a general error display area:
            // document.getElementById('general-error-area').textContent = "Chart could not be loaded: container missing.";
            return; // Stop execution if the container is not found
        }

        if (hasData) {
            var optionsCombined = {
                ...baseChartSettings,
                chart: { ...baseChartSettings.chart, id: "summaryTrendsChartInstance", type: 'bar' }, // Generic ID
                series: [
                    { name: 'Distance (m)', data: [...metersSeriesData] },
                    { name: 'Duration (s)', data: [...secondsSeriesData] },
                    { name: 'Pace (s/500m)', data: [...paceSeriesData] },
                    { name: 'Reps', data: [...repsSeriesData] }
                ],
                yaxis: [
                    { 
                        seriesName: 'Distance (m)',
                        opposite: false, // Ensure this is false or remove if it's the first axis
                        axisTicks: { show: true },
                        axisBorder: { show: true, color: baseChartSettings.colors[0] },
                        labels: {
                            style: { colors: baseChartSettings.colors[0] },
                            formatter: function (val) {
                                if (val === null || typeof val === 'undefined') return '';
                                const roundedVal = Math.round(val);
                                if (roundedVal >= 1000000) {
                                    return (roundedVal / 1000000).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 1 }) + " mln";
                            }
                            return roundedVal.toLocaleString();
                        }
                        },
                        title: {
                            text: "Distance (m)",
                            style: { color: baseChartSettings.colors[0] }
                        }
                    },
                    { 
                        seriesName: 'Duration (s)',
                        opposite: false, 
                        axisTicks: { show: true },
                        axisBorder: { show: true, color: baseChartSettings.colors[1] },
                        labels: {
                            style: { colors: baseChartSettings.colors[1] },
                            formatter: function(val) { 
                                const formatted = formatDurationTooltip(val);
                                return formatted !== null ? formatted : '';
                            }
                        },
                        title: {
                            text: "Duration (s)",
                            style: { color: baseChartSettings.colors[1] }
                        }
                    },
                    { 
                        seriesName: 'Pace (s/500m)',
                        opposite: false,
                        axisTicks: { show: true },
                        axisBorder: { show: true, color: baseChartSettings.colors[2] },
                        labels: {
                            style: { colors: baseChartSettings.colors[2] },
                            formatter: function(val) { 
                                 const formatted = formatPaceChartTooltip(val);
                                 return formatted !== null ? formatted : '';
                            }
                        },
                        title: {
                            text: "Pace (/500m)",
                            style: { color: baseChartSettings.colors[2] }
                        }
                    },
                    { 
                        seriesName: 'Reps',
                        opposite: false,
                        axisTicks: { show: true },
                        axisBorder: { show: true, color: baseChartSettings.colors[3] },
                        labels: {
                            style: { colors: baseChartSettings.colors[3] },
                            formatter: function (val) {
                                if (val === null || typeof val === 'undefined') return '';
                                const roundedVal = Math.round(val);
                                if (roundedVal >= 1000000) {
                                    return (roundedVal / 1000000).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 1 }) + " mln";
                            }
                            return roundedVal.toLocaleString();
                        }
                        },
                        title: {
                            text: "Reps", 
                            style: { color: baseChartSettings.colors[3] }
                        }
                    }
                ],
                tooltip: {
                    shared: true,
                    intersect: false,
                    custom: function({series, seriesIndex, dataPointIndex, w}) { // Use 'series' directly for active series
                        const categoryLabel = w.globals.labels[dataPointIndex] || (categoriesData && categoriesData[dataPointIndex]) || ''; // Use categoriesData
                        
                        let html = `<div class="apexcharts-tooltip-title" style="font-family: Helvetica, Arial, sans-serif; font-size: 12px;">${categoryLabel}</div>`;
                
                        // Iterate over visible series to build the tooltip
                        // w.globals.initialSeries contains all series, w.globals.series হচ্ছে বর্তমানে দৃশ্যমান সিরিজগুলো
                        // w.globals.series.map(...) is safer if you only want visible series in tooltip
                        // For shared tooltips, often you want all data for that x-point, so initialSeries is fine.
                        w.globals.initialSeries.forEach((s, i) => {
                            // Check if this series is currently visible (optional, but good for complex scenarios)
                            // if (w.globals.seriesVisibility[i]) { ... }

                            const seriesName = s.name; 
                            const Mvalue = s.data[dataPointIndex];
                            let formattedValue = 'N/A'; 
                
                            if (Mvalue !== null && typeof Mvalue !== 'undefined') {
                                if (seriesName === 'Distance (m)') {
                                    formattedValue = Math.round(Mvalue).toLocaleString();
                                } else if (seriesName === 'Duration (s)') {
                                    formattedValue = formatDurationTooltip(Mvalue);
                                } else if (seriesName === 'Pace (s/500m)') {
                                    const pace = formatPaceChartTooltip(Mvalue);
                                    formattedValue = pace ? pace + " /500m" : 'N/A';
                                } else if (seriesName === 'Reps') {
                                    formattedValue = formatRepsTooltip(Mvalue);
                                } else {
                                    formattedValue = Mvalue.toLocaleString(); 
                                }
                            }
                
                            const color = w.globals.colors[i];
                            html += `<div class="apexcharts-tooltip-series-group" style="display: flex; align-items: center; padding: 2px 5px;">` +
                                    `<span class="apexcharts-tooltip-marker" style="background-color: ${color}; width: 12px; height: 12px; margin-right: 5px; border-radius: 50%;"></span>` +
                                    `<div class="apexcharts-tooltip-text" style="font-family: Helvetica, Arial, sans-serif; font-size: 12px; white-space: nowrap;">` +
                                    `<span class="apexcharts-tooltip-text-y-label">${seriesName}: </span>` +
                                    `<span class="apexcharts-tooltip-text-y-value" style="font-weight: bold;">${formattedValue}</span>` +
                                    `</div>` +
                                    `</div>`;
                        });
                        return html;
                    }
                }
            };
            var combinedChart = new ApexCharts(chartContainer, optionsCombined); // Use generic ID selector
            combinedChart.render().then(() => {
                const seriesToHideByDefault = ['Duration (s)', 'Pace (s/500m)', 'Reps'];
                
                optionsCombined.series.forEach(seriesObj => {
                    if (seriesToHideByDefault.includes(seriesObj.name)) {
                        combinedChart.hideSeries(seriesObj.name);
                    } else if (seriesObj.name === 'Distance (m)') {
                        combinedChart.showSeries(seriesObj.name);
                    }
                });
            }).catch(function(error) {
                console.error("ApexCharts render error:", error);
                if (chartContainer) {
                    chartContainer.innerHTML = `<div style="text-align:center; padding:20px; color:red;">Error rendering chart: ${error.message}</div>`;
                }
            });
        } else {
            // Handle case where chartContainer exists but there's no data
            if (chartContainer) { // Check again, though it should exist if we passed the first check
                // The HTML templates already have a conditional message for no chart data,
                // so this might be redundant or you can refine it.
                // Example: chartContainer.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; min-height:350px;"><span style="color:#6a8fd7; font-size:1.2em;">[ No data to display in chart ]</span></div>';
            }
        }
    }