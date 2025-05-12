import React, { useEffect, useRef, useState } from 'react';
import { Box, CircularProgress, Grid, Paper, Typography, useTheme } from '@mui/material';
import {useWebSocketFrameNavigation} from "@/hooks/useWebsocketFrameNavigation";

interface ImageInfo {
  videoName: string;
  imageData: string; // base64 image data
}

const VideosViewer: React.FC = () => {
  const theme = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerDimensions, setContainerDimensions] = useState({ width: 0, height: 0 });

  // Use our WebSocket-based frame navigation hook
  const {
    currentFrame,
    frames,
    isLoading,
    error
  } = useWebSocketFrameNavigation();

  // Process images from the frame data
  const processedImages: Record<string, ImageInfo> = React.useMemo(() => {
    if (!frames) return {};

    const result: Record<string, ImageInfo> = {};
    Object.entries(frames).forEach(([videoName, imageData]) => {
      result[videoName] = {
        videoName,
        imageData,
      };
    });

    return result;
  }, [frames]);

  // Update container dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setContainerDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    updateDimensions();
    const resizeObserver = new ResizeObserver(updateDimensions);

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      if (containerRef.current) {
        resizeObserver.unobserve(containerRef.current);
      }
    };
  }, []);

  // Calculate optimal grid layout
  const { cols, rows } = React.useMemo(() => {
    const imageCount = Object.keys(processedImages).length;
    if (imageCount === 0) return { cols: 1, rows: 1 };

    // Simple grid calculation
    const cols = Math.ceil(Math.sqrt(imageCount));
    const rows = Math.ceil(imageCount / cols);

    return { cols, rows };
  }, [processedImages]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', width: '100%' }}>
        <Typography color="error">
          Error loading frame: {error ? String(error) : 'Unknown error'}
        </Typography>
      </Box>
    );
  }

  if (Object.keys(processedImages).length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Typography>No images available for this frame</Typography>
      </Box>
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        height: '100%',
        backgroundColor: theme.palette.background.default,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Grid
        container
        spacing={1}
        sx={{
          height: '100%',
          width: '100%',
          padding: 1,
          boxSizing: 'border-box',
        }}
      >
        {Object.values(processedImages).map((image) => (
          <Grid
            item
            key={image.videoName}
            xs={12 / cols}
            sx={{
              height: `${100 / rows}%`,
              padding: '4px',
              boxSizing: 'border-box',
            }}
          >
            <Paper
              elevation={3}
              sx={{
                height: '100%',
                width: '100%',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
              }}
            >
              <Box
                sx={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  backgroundColor: 'rgba(0,0,0,0.5)',
                  color: 'white',
                  padding: '2px 8px',
                  borderBottomRightRadius: '4px',
                  fontSize: '0.8rem',
                  zIndex: 1,
                }}
              >
                {image.videoName}
              </Box>
              <Box
                sx={{
                  height: '100%',
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                }}
              >
                <img
                  src={`data:image/jpeg;base64,${image.imageData}`}
                  alt={`${image.videoName}`}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain',
                  }}
                />
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default VideosViewer;
