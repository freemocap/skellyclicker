import React, { useEffect } from 'react';
import { Box, IconButton, Slider, Typography } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import { useAppDispatch, useAppSelector } from '@/store/AppStateStore';
import { setCurrentFrame, setIsPlaying } from '@/store/slices/playbackControlSlice';
import { useWebSocketFrameNavigation } from '@/hooks/useWebSocketFrameNavigation';

const PlaybackControls: React.FC = () => {
    const dispatch = useAppDispatch();
    const { isPlaying, currentFrame, totalFrames } = useAppSelector(state => state.playbackControl);
    const { goToNextFrame, goToPreviousFrame } = useWebSocketFrameNavigation();
    
    // Handle playback
    useEffect(() => {
        let intervalId: number | null = null;
        
        if (isPlaying) {
            intervalId = window.setInterval(() => {
                goToNextFrame();
            }, 100); // 10 FPS playback
        }
        
        return () => {
            if (intervalId !== null) {
                clearInterval(intervalId);
            }
        };
    }, [isPlaying, goToNextFrame]);

    const handleSliderChange = (_event: Event, newValue: number | number[]) => {
        dispatch(setCurrentFrame(newValue as number));
    };

    const togglePlayback = () => {
        dispatch(setIsPlaying(!isPlaying));
    };

    return (
        <Box sx={{ display: 'flex', alignItems: 'center', p: 2 }}>
            <IconButton onClick={goToPreviousFrame}>
                <SkipPreviousIcon />
            </IconButton>
            
            <IconButton onClick={togglePlayback}>
                {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
            </IconButton>
            
            <IconButton onClick={goToNextFrame}>
                <SkipNextIcon />
            </IconButton>
            
            <Slider
                value={currentFrame}
                min={0}
                max={Math.max(0, totalFrames - 1)}
                onChange={handleSliderChange}
                sx={{ mx: 2, flexGrow: 1 }}
            />
            
            <Typography variant="body2">
                {currentFrame + 1} / {totalFrames}
            </Typography>
        </Box>
    );
};

export default PlaybackControls;