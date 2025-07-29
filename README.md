# TTU Notes - Network Engineer's Web Application

A comprehensive web-based network engineering toolkit designed to streamline your workflow. Built with Python Flask, this application provides powerful SSH automation, intelligent device management, and advanced note-taking capabilities with modern UX design.

## 🚀 **Key Features**

### **🎨 Modern User Experience**
- **Dark Theme Interface** - Discord-inspired design with excellent readability
- **Responsive Design** - Works perfectly on desktop, tablet, and mobile
- **Interactive Dashboard** - Real-time statistics and quick access to all features
- **Smooth Animations** - Hover effects and transitions for professional feel
- **Keyboard Shortcuts** - Global and context-specific shortcuts for power users

### **📝 Advanced Note Management**
- **Smart Templates** - AI-powered template suggestions based on your device logs
- **Quick Notes** - Lightning-fast note creation with variable replacement
- **Auto-Save** - Never lose work with automatic draft saving
- **Advanced Search** - Filter by filename, content, date range, and tags
- **Bulk Operations** - Select and manage multiple notes simultaneously
- **Favorites System** - Star important notes for quick access
- **Export/Backup** - JSON export of all notes and metadata

### **🔧 SSH Automation & Device Management**
- **RADIUS Authentication** - Secure credential prompting without local storage
- **Multi-Vendor Support** - Cisco, Ciena, Nokia, Juniper devices
- **Automated Device Discovery** - Discover devices from your log analysis
- **Batch Operations** - Execute commands across multiple devices simultaneously
- **Command Library** - Comprehensive reference organized by vendor and category
- **Device Health Monitoring** - Real-time connectivity status
- **Configuration Backup** - Automated device configuration backups

### **🤖 Intelligent Features**
- **Smart Template Suggestions** - AI analyzes your logs to suggest relevant templates
- **Automated Device Discovery** - Parse device names from logs to auto-populate device list
- **Log Analysis & Search** - Index and search through thousands of historical device logs
- **Command Pattern Recognition** - Learn from your usage to suggest improvements
- **Device Type Auto-Detection** - Automatic device type detection based on naming

## 🎯 **Device Support**

### **Ciena Devices**
- **CN-3903, CN-3916, CN-3930, CN-3924, 5160, 5170**
- Light level checks, performance monitoring, alarm management
- Fiber troubleshooting workflows, CFM monitoring

### **Cisco Devices**
- **ASR9k and NCS5500 series**
- BGP troubleshooting, interface diagnostics
- Platform-specific commands and statistics

### **Nokia Devices**
- **7250 IXR and 7750 series**
- Port statistics, router interface management
- BGP and routing protocol commands

### **Juniper Devices**
- **MX and ACX series**
- Interface management, routing table analysis
- Configuration and system monitoring

## 🏠 **Dashboard Overview**

The enhanced home page provides:

- **Welcome Section** - Current date and application overview
- **Quick Stats** - Real-time counts of templates, devices, notes, and quick notes
- **Feature Cards** - Beautiful gradient cards for all major features:
  - AI-Powered Template Suggestions
  - Automated Device Discovery
  - Batch Operations
  - Device Management
  - Command Library
  - Quick Notes
- **Template Categories** - Organized template display with filtering

## 🎮 **Keyboard Shortcuts**

### **Global Shortcuts**
- `Ctrl+H` - Go to Home
- `Ctrl+N` - Go to Notes
- `Ctrl+Q` - Go to Quick Notes
- `Ctrl+T` - Go to Templates
- `Ctrl+S` - Go to Scripts
- `Ctrl+/` - Show keyboard shortcuts help

### **Note Shortcuts**
- `Ctrl+C` - Copy note content
- `Ctrl+E` - Edit note
- `Ctrl+F` - Toggle favorites
- `Ctrl+D` - Delete note
- `Ctrl+V` - Replace variables (Quick Notes)

## 📋 **Prerequisites**

- **Python 3.8+**
- **Windows/Linux/macOS**
- **Network access to managed devices**
- **RADIUS authentication credentials**

## 🛠️ **Installation**

### **1. Clone the Repository**
```bash
git clone <repository-url>
cd TTU
```

### **2. Create Virtual Environment**
```bash
python -m venv venv
```

### **3. Activate Virtual Environment**
**Windows:**
```bash
venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
source venv/bin/activate
```

### **4. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **5. Run the Application**
```bash
python app.py
```

The application will be available at `http://127.0.0.1:5000`

## 🎯 **Usage Guide**

### **Getting Started**
1. **Home Dashboard** - Overview of all features and quick stats
2. **Add Devices** - Manage your network devices for SSH automation
3. **Create Templates** - Build reusable command templates
4. **Execute Commands** - Run commands on individual or multiple devices
5. **Take Notes** - Document your work with the advanced note system

### **Device Management**
- **Add Devices** - Enter device names/IPs and device types
- **Device Discovery** - Automatically discover devices from your logs
- **Batch Operations** - Execute commands across multiple devices
- **Health Monitoring** - Check device connectivity status

### **Template System**
- **Smart Suggestions** - Get AI-powered template recommendations
- **Category Management** - Organize templates by type (Network, Customer, etc.)
- **Variable Replacement** - Use {variable} syntax for dynamic content
- **Quick Access** - Use templates directly from the dashboard

### **Note Taking**
- **Quick Notes** - Fast command templates with auto-save
- **Advanced Search** - Find notes by content, tags, or date
- **Bulk Operations** - Manage multiple notes at once
- **Export/Import** - Backup and restore your notes

### **Command Library**
- **Vendor-Specific** - Commands organized by Cisco, Ciena, Nokia, Juniper
- **Category-Based** - Commands grouped by function (show, configure, etc.)
- **Searchable** - Find commands quickly with search functionality
- **Editable** - Add, edit, and organize commands as needed

## 🔧 **Advanced Features**

### **Log Analysis**
- **Historical Log Processing** - Analyze thousands of device logs
- **Command Extraction** - Automatically extract commands from logs
- **Pattern Recognition** - Identify common command patterns
- **Device Discovery** - Find devices mentioned in logs

### **Batch Operations**
- **Multi-Device Execution** - Run commands on multiple devices simultaneously
- **Progress Tracking** - Real-time status updates during execution
- **Result Aggregation** - Combined results from all devices
- **Template Support** - Use predefined batch operation templates

### **Smart Suggestions**
- **Template Recommendations** - AI suggests relevant templates based on your logs
- **Command Suggestions** - Get command recommendations for specific devices
- **Workflow Optimization** - Identify patterns to improve your processes

## 📁 **File Structure**

```
TTU/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # HTML templates
│   ├── base.html         # Base template with navigation
│   ├── home.html         # Enhanced dashboard
│   ├── manage_devices.html # Device management
│   └── ...               # Other templates
├── saved_notes/          # Saved notes and metadata
├── scripts/              # Python automation scripts
├── devices.json          # Device configuration
└── logs_index.json       # Log analysis index
```

## 🔒 **Security Features**

- **RADIUS Authentication** - No local credential storage
- **Secure Credential Prompting** - Credentials requested per session
- **Audit Logging** - Track all actions and commands
- **No Password Rotation** - Credentials managed externally

## 🚀 **Performance Features**

- **Responsive Design** - Optimized for all screen sizes
- **Fast Loading** - Efficient template rendering and data handling
- **Auto-Save** - Prevent data loss with automatic saving
- **Background Processing** - Handle long-running operations

## 🤝 **Contributing**

This application is designed for network engineers working with:
- **Multi-vendor environments** (Cisco, Ciena, Nokia, Juniper)
- **RADIUS authentication** systems
- **Distributed network infrastructure**
- **Regular device maintenance and troubleshooting**

## 📞 **Support**

For issues, questions, or feature requests:
1. Check the keyboard shortcuts (`Ctrl+/`)
2. Review the template system for common tasks
3. Use the device discovery feature for large environments
4. Leverage batch operations for efficiency

## 🎉 **What's New**

### **Latest Updates**
- ✅ **Enhanced Home Dashboard** - Beautiful new interface with statistics
- ✅ **Improved Device Management** - Better layout and organization
- ✅ **Keyboard Shortcuts** - Global and context-specific shortcuts
- ✅ **Smart Template Suggestions** - AI-powered recommendations
- ✅ **Automated Device Discovery** - Discover devices from logs
- ✅ **Batch Operations** - Multi-device command execution
- ✅ **Log Analysis** - Process and search historical logs
- ✅ **Command Library** - Comprehensive command reference
- ✅ **Dark Theme** - Modern, professional interface
- ✅ **Mobile Responsive** - Works on all devices

---

**Built for Network Engineers, by Network Engineers** 🛠️ 