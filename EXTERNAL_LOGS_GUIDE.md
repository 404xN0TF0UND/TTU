# External Logs Integration Guide

TTU Notes now supports importing and monitoring external SecureCRT log folders, allowing you to analyze logs from your existing SecureCRT setup without moving files.

## Features

- **Import Existing Logs**: Add your SecureCRT logs folder to TTU Notes
- **Folder Monitoring**: Automatically detect new log files
- **Unified Search**: Search across all log sources (internal + external)
- **Analytics**: Get insights from all your logs combined

## Setup Instructions

### 1. Access Logs Configuration

1. Navigate to **Advanced** → **Logs Configuration** in the main menu
2. Or go to **Logs Dashboard** → **Configuration** button

### 2. Add Your SecureCRT Logs Folder

1. In the "Add External Log Folder" section:
   - **Folder Name**: Enter a friendly name (e.g., "SecureCRT Logs")
   - **Folder Path**: Enter the full path to your SecureCRT logs folder
   
   **Common SecureCRT Log Paths:**
   - Windows: `C:\Users\username\Documents\SecureCRT\Logs`
   - Windows (AppData): `C:\Users\username\AppData\Roaming\VanDyke\SecureCRT\Logs`
   - Custom location: Check your SecureCRT settings

2. Click **Add Folder**

### 3. Enable Folder Monitoring (Optional)

1. In the "Folder Monitoring" section:
   - Click the toggle button to enable automatic monitoring
   - When enabled, TTU Notes will automatically detect new log files

### 4. Rebuild Index

1. Click **Rebuild Logs Index** to scan all configured folders
2. This will index all log files from both internal and external sources

## Using External Logs

### Viewing Logs

- **Logs Dashboard**: See statistics from all log sources
- **Search Logs**: Search across all indexed logs
- **Logs Analytics**: Get insights from combined log data

### Checking for New Logs

- **Manual Check**: Click "Check New Logs" button on the dashboard
- **Automatic**: If monitoring is enabled, new logs are detected automatically

### Managing External Folders

- **View Status**: See which folders are available/not found
- **Remove Folders**: Remove folders you no longer need
- **Update Paths**: Remove and re-add if folder paths change

## File Format Support

TTU Notes supports SecureCRT log files with the following naming convention:
```
YYYY-MM-DD-HH-MM-SS.mmm__device_name(device_name).txt
```

Example:
```
2024-01-15-14-30-25.123__router1(192.168.1.1).txt
```

## Troubleshooting

### Folder Not Found
- Verify the folder path is correct
- Ensure the folder exists and is accessible
- Check for typos in the path

### No Logs Appearing
- Ensure log files have `.txt` extension
- Check that files follow the SecureCRT naming convention
- Try rebuilding the index

### Monitoring Not Working
- Verify folder monitoring is enabled
- Check that external folders are marked as "Available"
- Manually check for new logs using the button

## Best Practices

1. **Use Descriptive Names**: Give your external folders meaningful names
2. **Regular Index Rebuilds**: Rebuild index periodically for large log collections
3. **Monitor Storage**: Large log folders may impact performance
4. **Backup Configuration**: Your logs configuration is saved in `logs_config.json`

## Security Notes

- TTU Notes only reads log files, it doesn't modify them
- External folder paths are stored locally in `logs_config.json`
- No log data is transmitted outside your system
- Folder access is limited to the paths you explicitly configure

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your SecureCRT log format
3. Ensure folder permissions are correct
4. Try removing and re-adding the external folder 