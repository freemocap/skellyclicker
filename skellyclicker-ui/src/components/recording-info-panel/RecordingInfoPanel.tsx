import React, { useState, useEffect } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
  useTheme,
  Alert,
  Button
} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FolderIcon from '@mui/icons-material/Folder';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useLoadRecording } from "@/hooks/useLoadRecording";
import {FolderExplorer} from "@/components/recording-info-panel/FolderExplorer";

// Local storage key for saving the selected path
const SELECTED_PATH_STORAGE_KEY = 'skellyclicker-selected-recording-path';

export const RecordingInfoPanel: React.FC = () => {
  const theme = useTheme();
  const { recordingInfo, loadRecording, isLoadingRecording, isLoadingError, loadingError } = useLoadRecording();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  // Load the saved path from localStorage on component mount
  useEffect(() => {
    const savedPath = localStorage.getItem(SELECTED_PATH_STORAGE_KEY);
    if (savedPath) {
      setSelectedPath(savedPath);
      loadRecording(savedPath).catch(error => {
        console.error('Failed to load saved recording path:', error);
      });
    }
  }, [loadRecording]);

  const handleSelectDirectory = async () => {
    // If dialog is already open or loading is in progress, don't open another dialog
    if (isDialogOpen || isLoadingRecording) return;

    try {
      setIsDialogOpen(true);
      const newSelectedPath = await window.electronAPI.selectDirectory();
      if (newSelectedPath) {
        setSelectedPath(newSelectedPath);
        // Save the selected path to localStorage
        localStorage.setItem(SELECTED_PATH_STORAGE_KEY, newSelectedPath);
      }
    } catch (error) {
      console.error('Failed to select directory:', error);
    } finally {
      setIsDialogOpen(false);
    }
  };

  const handleLoadRecording = async () => {
    if (!selectedPath || isLoadingRecording) return;

    try {
      await loadRecording(selectedPath);
    } catch (error) {
      console.error('Failed to load recording:', error);
    }
  };

  const handleOpenFolder = async () => {
    if (!selectedPath) return;

    try {
      await window.electronAPI.openFolder(selectedPath);
    } catch (error) {
      console.error('Failed to open folder:', error);
    }
  };

  // Determine if buttons should be disabled
  const isButtonDisabled = isDialogOpen || isLoadingRecording;

  // Create path parts for visualization
  const renderPathDisplay = () => {
    if (!selectedPath) return null;

    // Extract directory and filename parts
    const pathParts = selectedPath.split(/[/\\]/);
    const filename = pathParts[pathParts.length - 1];
    const directory = pathParts.slice(0, -1).join('/');
    const fullPath = selectedPath;

    const parts = [
      { icon: <FolderIcon fontSize="small" />, text: directory },
      { icon: <FolderIcon fontSize="small" />, text: filename }
    ];

    return (
      <Paper
        elevation={0}
        sx={{
          p: 1.5,
          backgroundColor: theme.palette.mode === 'dark'
            ? 'rgba(255, 255, 255, 0.05)'
            : 'rgba(0, 0, 0, 0.04)',
          borderRadius: 1,
          borderStyle: 'solid',
          borderColor: theme.palette.divider,
        }}
      >
        <Box sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 1
        }}>
          {/* Mobile/Narrow view */}
          <Box sx={{ display: { xs: 'block', md: 'none' } }}>
            <Tooltip title={fullPath} placement="bottom-start">
              <Typography
                noWrap
                sx={{
                  fontFamily: 'monospace',
                  fontSize: '0.9rem',
                  cursor: 'pointer'
                }}
              >
                {fullPath}
              </Typography>
            </Tooltip>
          </Box>

          {/* Desktop view */}
          <Box
            sx={{
              display: { xs: 'none', md: 'flex' },
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 0.5
            }}
          >
            {parts.map((part, index) => (
              <React.Fragment key={index}>
                <Box sx={{
                  display: 'flex',
                  alignItems: 'center',
                  color: 'text.secondary',
                  borderRadius: 1,
                  px: 1,
                  py: 0.5,
                }}>
                  {part.icon}
                  <Typography
                    sx={{
                      ml: 0.5,
                      fontFamily: 'monospace',
                      fontSize: '0.9rem'
                    }}
                  >
                    {part.text}
                  </Typography>
                </Box>
                {index < parts.length - 1 && (
                  <ChevronRightIcon sx={{ color: 'text.secondary' }} />
                )}
              </React.Fragment>
            ))}
          </Box>

          <Tooltip title="Open folder in file explorer">
            <IconButton
              size="small"
              onClick={handleOpenFolder}
              sx={{
                color: theme.palette.primary.main,
                '&:hover': {
                  backgroundColor: theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.08)'
                    : 'rgba(0, 0, 0, 0.04)'
                }
              }}
            >
              <FolderOpenIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>
    );
  };

  return (
    <Accordion
      defaultExpanded
      sx={{
        borderRadius: 2,
        '&:before': { display: 'none' },
        boxShadow: theme.shadows[3]
      }}
    >
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        backgroundColor: theme.palette.primary.main,
        borderTopLeftRadius: 8,
        borderTopRightRadius: 8,
      }}>
        <AccordionSummary
          expandIcon={<ExpandMoreIcon sx={{ color: theme.palette.primary.contrastText }} />}
          sx={{
            flex: 1,
            color: theme.palette.primary.contrastText,
            '&:hover': {
              backgroundColor: theme.palette.primary.light,
            }
          }}
        >
          <Typography variant="subtitle1">Recording Selection</Typography>
        </AccordionSummary>

        <IconButton
          onClick={handleSelectDirectory}
          disabled={isButtonDisabled}
          sx={{
            mr: 2,
            color: theme.palette.primary.contrastText,
            '&:hover': {
              backgroundColor: theme.palette.primary.light,
            }
          }}
        >
          {isLoadingRecording || isDialogOpen ?
            <CircularProgress size={24} color="inherit" /> :
            <FolderOpenIcon />
          }
        </IconButton>
      </Box>

      <AccordionDetails sx={{ p: 2, bgcolor: 'background.default' }}>
        <Paper
          elevation={0}
          sx={{
            bgcolor: 'background.paper',
            borderRadius: 2,
            overflow: 'hidden',
            p: 2
          }}
        >
          <Stack spacing={2}>
            {selectedPath ? (
              <>
                <Typography variant="body1">
                  Selected Directory: {selectedPath.split(/[/\\]/).pop()}
                </Typography>
                {renderPathDisplay()}

                <Box sx={{ display: 'flex', gap: 2 }}>
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={isLoadingRecording ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
                    onClick={handleLoadRecording}
                    disabled={isButtonDisabled}
                    sx={{ flexGrow: 1 }}
                  >
                    {isLoadingRecording ? 'Loading...' : 'Load Recording'}
                  </Button>
                </Box>

                {isLoadingRecording && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CircularProgress size={20} />
                    <Typography variant="body2">Loading recording data...</Typography>
                  </Box>
                )}

                {isLoadingError && (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    Failed to load recording: {loadingError?.toString() || 'Unknown error'}
                  </Alert>
                )}
                  {/*<Box sx={{ mt: 2 }}>*/}
                  {/*    <Typography variant="subtitle2" sx={{ mb: 1 }}>*/}
                  {/*        Folder Contents:*/}
                  {/*    </Typography>*/}
                  {/*    <FolderExplorer folderPath={selectedPath} />*/}
                  {/*</Box>*/}
                {recordingInfo && (
                  <>
                    <Typography variant="body2">
                      Recording Name: {recordingInfo.recording_name}
                    </Typography>
                    <Typography variant="body2">
                      Total Frames: {recordingInfo.frame_count}
                    </Typography>
                    <Typography variant="body2">
                      Video Files: {recordingInfo.video_paths.length}
                    </Typography>
                  </>
                )}
              </>
            ) : (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2
                }}
              >
                <Typography variant="body1" align="center">
                  No recording selected
                </Typography>
                <Box
                  onClick={isButtonDisabled ? undefined : handleSelectDirectory}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    p: 2,
                    borderRadius: 2,
                    border: `1px dashed ${theme.palette.divider}`,
                    cursor: isButtonDisabled ? 'not-allowed' : 'pointer',
                    opacity: isButtonDisabled ? 0.7 : 1,
                    transition: 'all 0.2s',
                    '&:hover': {
                      backgroundColor: isButtonDisabled ? 'transparent' : theme.palette.action.hover,
                      borderColor: isButtonDisabled ? theme.palette.divider : theme.palette.primary.main,
                    }
                  }}
                >
                  {isLoadingRecording || isDialogOpen ? (
                    <CircularProgress size={24} color="primary" />
                  ) : (
                    <FolderOpenIcon color="primary" />
                  )}
                  <Typography color="primary">
                    {isLoadingRecording ? 'Loading recording...' :
                     isDialogOpen ? 'Selecting folder...' :
                     'Click to select a recording directory'}
                  </Typography>
                </Box>
              </Box>
            )}
          </Stack>
        </Paper>
      </AccordionDetails>
    </Accordion>
  );
};
