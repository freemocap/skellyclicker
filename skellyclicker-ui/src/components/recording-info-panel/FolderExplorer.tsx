import React, { useState, useEffect } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Collapse,
  CircularProgress,
  Typography,
  Paper,
  useTheme
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

interface FileItem {
  name: string;
  path: string;
  isDirectory: boolean;
  size?: number;
  lastModified?: Date;
}

interface FolderExplorerProps {
  folderPath: string | null;
}

export const FolderExplorer: React.FC<FolderExplorerProps> = ({ folderPath }) => {
  const theme = useTheme();
  const [contents, setContents] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});
  const [folderContents, setFolderContents] = useState<Record<string, FileItem[]>>({});

  useEffect(() => {
    if (!folderPath) {
      setContents([]);
      setError(null);
      return;
    }

    const loadFolderContents = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const items = await window.electronAPI.getFolderContents(folderPath);
        setContents(items);
      } catch (err) {
        console.error('Failed to load folder contents:', err);
        setError(`Failed to load folder contents: ${err instanceof Error ? err.message : String(err)}`);
        setContents([]);
      } finally {
        setLoading(false);
      }
    };

    loadFolderContents();
  }, [folderPath]);

  const handleToggleFolder = async (folder: FileItem) => {
    const isExpanded = expandedFolders[folder.path] || false;
    
    // Update expanded state
    setExpandedFolders(prev => ({
      ...prev,
      [folder.path]: !isExpanded
    }));

    // If expanding and we don't have contents yet, load them
    if (!isExpanded && !folderContents[folder.path]) {
      try {
        const items = await window.electronAPI.getFolderContents(folder.path);
        setFolderContents(prev => ({
          ...prev,
          [folder.path]: items
        }));
      } catch (err) {
        console.error(`Failed to load contents of ${folder.path}:`, err);
      }
    }
  };

  const renderFileItem = (item: FileItem, level: number = 0) => {
    const isExpanded = expandedFolders[item.path] || false;
    const nestedItems = folderContents[item.path] || [];
    
    return (
      <React.Fragment key={item.path}>
        <ListItem 
          button 
          onClick={() => item.isDirectory && handleToggleFolder(item)}
          sx={{ 
            pl: 2 + level * 2,
            borderRadius: 1,
            mb: 0.5,
            '&:hover': {
              backgroundColor: theme.palette.action.hover
            }
          }}
        >
          <ListItemIcon sx={{ minWidth: 36 }}>
            {item.isDirectory ? (
              isExpanded ? <ExpandMoreIcon color="primary" /> : <ChevronRightIcon color="primary" />
            ) : (
              <InsertDriveFileIcon color="disabled" fontSize="small" />
            )}
          </ListItemIcon>
          
          <ListItemIcon sx={{ minWidth: 36 }}>
            {item.isDirectory ? (
              <FolderIcon sx={{ color: theme.palette.primary.light }} />
            ) : (
              <InsertDriveFileIcon fontSize="small" />
            )}
          </ListItemIcon>
          
          <ListItemText 
            primary={item.name} 
            primaryTypographyProps={{ 
              noWrap: true,
              sx: { 
                fontSize: '0.9rem',
                fontWeight: item.isDirectory ? 500 : 400
              } 
            }}
          />
        </ListItem>
        
        {item.isDirectory && (
          <Collapse in={isExpanded} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              {nestedItems.length > 0 ? (
                nestedItems.map(childItem => renderFileItem(childItem, level + 1))
              ) : (
                <ListItem sx={{ pl: 4 + level * 2 }}>
                  <ListItemText 
                    primary="Empty folder" 
                    primaryTypographyProps={{ 
                      sx: { 
                        fontSize: '0.85rem',
                        fontStyle: 'italic',
                        color: theme.palette.text.secondary
                      } 
                    }}
                  />
                </ListItem>
              )}
            </List>
          </Collapse>
        )}
      </React.Fragment>
    );
  };

  if (!folderPath) {
    return (
      <Paper 
        elevation={0} 
        sx={{ 
          p: 3, 
          textAlign: 'center',
          backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
          borderRadius: 2
        }}
      >
        <Typography variant="body1" color="text.secondary">
          No folder selected
        </Typography>
      </Paper>
    );
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress size={24} />
        <Typography variant="body2" sx={{ ml: 2 }}>
          Loading folder contents...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Paper 
        elevation={0} 
        sx={{ 
          p: 3, 
          backgroundColor: theme.palette.error.light,
          color: theme.palette.error.contrastText,
          borderRadius: 2
        }}
      >
        <Typography variant="body2">{error}</Typography>
      </Paper>
    );
  }

  return (
    <Paper 
      elevation={0} 
      sx={{ 
        p: 1,
        backgroundColor: theme.palette.background.paper,
        borderRadius: 2,
        maxHeight: '400px',
        overflow: 'auto'
      }}
    >
      <List dense component="nav" aria-label="folder contents">
        {contents.length > 0 ? (
          contents.map(item => renderFileItem(item))
        ) : (
          <ListItem>
            <ListItemText 
              primary="Empty folder" 
              primaryTypographyProps={{ 
                sx: { 
                  fontStyle: 'italic',
                  color: theme.palette.text.secondary
                } 
              }}
            />
          </ListItem>
        )}
      </List>
    </Paper>
  );
};