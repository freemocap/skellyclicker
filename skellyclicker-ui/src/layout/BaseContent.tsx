// skellyclicker-ui/src/layout/BaseContent.tsx
import React from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Copyright} from "@/components/layout-components/Copyright";
import {useTheme} from "@mui/material/styles";
import VideosViewer from "@/components/VideosView";
import PlaybackView from "@/components/PlaybackView";

export const BaseContent = () => {
    const theme = useTheme();

    return (
        <React.Fragment>
            <Box sx={{
                py: 1,
                px: 1,
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                width: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: theme.palette.divider
            }}>
                <Box sx={{
                    flex: 1,
                    display: 'flex',
                    width: '100%',
                    justifyContent: 'center',
                    alignItems: 'center',
                    overflow: 'hidden',
                }}>
                    <ErrorBoundary>
                        <PlaybackView />
                    </ErrorBoundary>
                </Box>
                <Box component="footer" sx={{p: 1}}>
                    <Copyright />
                </Box>
            </Box>
        </React.Fragment>
    )
}
