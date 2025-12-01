# MovieAnalyzer

A comprehensive video analysis tool using PySceneDetect to analyze scene detection metrics and visualize content values.

## Features

- **Scene Detection**: Uses PySceneDetect's ContentDetector to identify scene boundaries
- **Statistical Analysis**: Computes mean, median, standard deviation, and other statistics
- **Histogram Visualization**: Shows distribution of content values
- **Time Series Plot**: Displays content values over time with scene boundaries marked
- **Interactive Preview**: Move your mouse over the time series to see video thumbnails at that moment
- **Threshold Optimization**: Automatically finds the threshold to produce a target number of scenes

## Requirements

```bash
pip install scenedetect[opencv] opencv-python numpy matplotlib
```

Or:

```bash
pip install scenedetect opencv-python-headless numpy matplotlib
```

## Usage

### Basic Analysis

```bash
./movie_analyzer.py your_video.mp4
```

This will:
1. Analyze the video using the default threshold (27.0)
2. Print statistics (mean, median, etc.)
3. Show a histogram of content values
4. Show an interactive time series plot

### Target a Specific Number of Scenes

```bash
./movie_analyzer.py your_video.mp4 --scenecount 10
```

This will automatically find the threshold that produces approximately 10 scenes.

### Custom Threshold

```bash
./movie_analyzer.py your_video.mp4 --threshold 35.0
```

### Save Statistics to CSV

```bash
./movie_analyzer.py your_video.mp4 --output stats.csv
```

The CSV file will contain: Frame Number, Timecode, Content Val

### Save Visualizations

```bash
./movie_analyzer.py your_video.mp4 \
    --save-histogram histogram.png \
    --save-timeseries timeseries.png
```

### Disable Interactive Mode

If you want to save plots without the interactive preview:

```bash
./movie_analyzer.py your_video.mp4 --no-interactive
```

### Complete Example

```bash
./movie_analyzer.py ~/videos/my_movie.mp4 \
    --scenecount 15 \
    --output analysis.csv \
    --save-histogram hist.png \
    --save-timeseries series.png \
    --hist-bins 100
```

## Command-Line Options

```
positional arguments:
  video                 Path to video file

optional arguments:
  -h, --help            show this help message and exit
  -c SCENECOUNT, --scenecount SCENECOUNT
                        Target number of scenes (will compute optimal threshold)
  -t THRESHOLD, --threshold THRESHOLD
                        Content detection threshold (default: 27.0)
  -o OUTPUT, --output OUTPUT
                        Save statistics to CSV file
  --hist-bins HIST_BINS
                        Number of bins for histogram (default: 50)
  --no-interactive      Disable interactive thumbnail preview
  --save-histogram SAVE_HISTOGRAM
                        Save histogram to file
  --save-timeseries SAVE_TIMESERIES
                        Save time series plot to file
```

## Interactive Features

When viewing the time series plot (default behavior), you can:

- **Move your mouse** over the plot to see a thumbnail of the video at that time
- The **red vertical lines** indicate detected scene boundaries
- A **red cursor** follows your mouse to help pinpoint exact times

This makes it easy to visually inspect what's happening at different content value peaks and valleys.

## Understanding Content Values

The "content value" represents the amount of change between consecutive frames:

- **Low values** (~0-10): Little change between frames (static scenes)
- **Medium values** (~10-30): Moderate motion or gradual changes
- **High values** (>30): Significant changes (scene cuts, fast motion)

The default threshold of 27.0 is a good starting point, but you may need to adjust based on your video:

- **Increase threshold**: Detect fewer scenes (only major cuts)
- **Decrease threshold**: Detect more scenes (including subtle transitions)

## Using as a Python Module

You can also import and use the MovieAnalyzer class in your own scripts:

```python
from movie_analyzer import MovieAnalyzer

# Create analyzer
analyzer = MovieAnalyzer('my_video.mp4')

# Run analysis
analyzer.analyze(threshold=27.0)

# Get statistics
stats = analyzer.get_statistics()
print(f"Mean content value: {stats['mean']:.2f}")

# Access raw data
print(f"Number of frames: {len(analyzer.content_vals)}")
print(f"Number of scenes: {len(analyzer.scenes)}")

# Create visualizations
analyzer.plot_histogram()
analyzer.plot_timeseries(interactive=True)

# Save to CSV
analyzer.save_stats_csv('output.csv')

# Find optimal threshold for N scenes
threshold = analyzer.compute_threshold_for_scene_count(target_scene_count=10)
```

## Troubleshooting

### "No module named 'scenedetect'"

Install PySceneDetect:
```bash
pip install scenedetect[opencv]
```

### Interactive preview not working

Make sure you have a GUI backend for matplotlib. If running on a server, use:
```bash
./movie_analyzer.py your_video.mp4 --no-interactive
```

### Video file not found

Provide the full path to your video:
```bash
./movie_analyzer.py ~/path/to/your/video.mp4
```

## Tips

1. Start with the default threshold and adjust based on results
2. Use `--scenecount` if you know roughly how many scenes you expect
3. The interactive preview is great for understanding what triggers scene changes
4. Save the CSV output for further analysis in other tools
5. Different video types may need different thresholds:
   - Movies/TV: 27.0 (default)
   - Fast-paced action: 35.0+
   - Slow documentaries: 15.0-25.0

## License

This tool uses PySceneDetect and OpenCV. Please refer to their respective licenses.
