import React, {useEffect, useRef} from 'react';
import {Box, IconButton, Slider, Stack, TextField, Typography} from '@mui/material';
import {Pause, PlayArrow, SkipNext, SkipPrevious} from '@mui/icons-material';
import {useAppDispatch, useAppSelector} from '@/store/AppStateStore';
import {
    nextFrame,
    previousFrame,
    setCurrentFrame,
    setIsPlaying,
    setStepSize,
} from '@/store/slices/playbackControlSlice';

const PlaybackControls: React.FC = () => {
  const dispatch = useAppDispatch();
  const {
    isPlaying,
    currentFrame,
    stepSize,
    totalFrames
  } = useAppSelector(state => state.playbackControl);

  const playbackInterval = useRef<number | null>(null);

  // Handle playback logic
  useEffect(() => {
    if (isPlaying) {
      // Clear any existing interval
      if (playbackInterval.current) {
        window.clearInterval(playbackInterval.current);
      }

      // Set new interval based on playback rate
      const intervalTime = 1000 / 60; // Default to 60 FPS
      playbackInterval.current = window.setInterval(() => {
        dispatch(nextFrame());
      }, intervalTime);
    } else if (playbackInterval.current) {
      // Clear interval when not playing
      window.clearInterval(playbackInterval.current);
      playbackInterval.current = null;
    }

    // Cleanup on unmount
    return () => {
      if (playbackInterval.current) {
        window.clearInterval(playbackInterval.current);
      }
    };
  }, [isPlaying, dispatch]);

  const handlePlayPause = () => {
    dispatch(setIsPlaying(!isPlaying));
  };

  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    dispatch(setCurrentFrame(newValue as number));
  };

  const handleStepSizeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(event.target.value, 10);
    if (!isNaN(value) && value > 0) {
      dispatch(setStepSize(value));
    }
  };



  return (
    <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
      <Stack spacing={2}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <IconButton onClick={() => dispatch(previousFrame())}>
            <SkipPrevious />
          </IconButton>

          <IconButton onClick={handlePlayPause}>
            {isPlaying ? <Pause /> : <PlayArrow />}
          </IconButton>

          <IconButton onClick={() => dispatch(nextFrame())}>
            <SkipNext />
          </IconButton>

          <Typography variant="body2" sx={{ minWidth: 100 }}>
            Frame: {currentFrame} / {totalFrames > 0 ? totalFrames - 1 : 0}
          </Typography>



          <TextField
            label="Step Size"
            type="number"
            size="small"
            value={stepSize}
            onChange={handleStepSizeChange}
            InputProps={{ inputProps: { min: 1 } }}
            sx={{ width: 100 }}
          />
        </Box>

        <Slider
          value={currentFrame}
          min={0}
          max={Math.max(0, totalFrames - 1)}
          onChange={handleSliderChange}
          disabled={totalFrames <= 0}
        />
      </Stack>
    </Box>
  );
};

export default PlaybackControls;
