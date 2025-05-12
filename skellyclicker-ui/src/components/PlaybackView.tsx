import React, {useEffect} from 'react';
import {Box} from '@mui/material';
import PlaybackControls from './PlaybackControls';
import {useAppDispatch} from '@/store/AppStateStore';
import {setTotalFrames} from '@/store/slices/playbackControlSlice';
import VideosViewer from "@/components/VideosView";
import {useLoadRecording} from "@/hooks/useLoadRecording";


const PlaybackView: React.FC = () => {




    return (
        <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            width: '100%'
        }}>
            <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
                <VideosViewer />
            </Box>
            <PlaybackControls />
        </Box>
    );
};

export default PlaybackView;
