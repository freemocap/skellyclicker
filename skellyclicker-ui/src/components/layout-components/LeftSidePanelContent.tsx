// skellyclicker-ui/src/components/ui-components/LeftSidePanelContent.tsx
import * as React from 'react';
import Box from "@mui/material/Box";
import {List, ListItem, useTheme} from "@mui/material";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";
import ThemeToggle from "@/components/layout-components/ThemeToggle";

// Extract reusable scrollbar styles
const scrollbarStyles = {
  '&::-webkit-scrollbar': {
    width: '8px',
    backgroundColor: 'transparent',
  },
  '&::-webkit-scrollbar-thumb': {
    backgroundColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
      ? 'rgba(255, 255, 255, 0.2)'
      : 'rgba(0, 0, 0, 0.2)',
    borderRadius: '4px',
    '&:hover': {
      backgroundColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.3)'
        : 'rgba(0, 0, 0, 0.3)',
    },
  },
  '&::-webkit-scrollbar-track': {
    backgroundColor: 'transparent',
  },
  scrollbarWidth: 'thin',
  scrollbarColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
    ? 'rgba(255, 255, 255, 0.2) transparent'
    : 'rgba(0, 0, 0, 0.2) transparent',
};

export const LeftSidePanelContent = () => {
    const theme = useTheme();

    // Dynamic styles based on theme
    const item = {
        py: '2px',
        px: 3,
        color: theme.palette.primary.contrastText,
        '&:hover, &:focus': {
            bgcolor: theme.palette.mode === 'dark'
                ? 'rgba(255, 255, 255, 0.08)'
                : 'rgba(0, 0, 0, 0.04)',
        },
    };

    const itemCategory = {
        boxShadow: theme.palette.mode === 'dark'
            ? '0 -1px 0 rgb(255,255,255,0.1) inset'
            : '0 -1px 0 rgba(0,0,0,0.1) inset',
        py: 1.5,
        px: 3,
    };

    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            backgroundColor: theme.palette.primary.dark,
            color: theme.palette.primary.contrastText,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
        }}>
            <List disablePadding>
                <ListItem sx={{...item, ...itemCategory, fontSize: 22, color: theme.palette.common.white}}>
                    SkellyClicker💀👆
                    <ThemeToggle />

                </ListItem>
            </List>

            <Box sx={{
                flex: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
                ...scrollbarStyles
            }}>
                <RecordingInfoPanel/>
                {/*<WebsocketConnectionStatus/>*/}
            </Box>
        </Box>
    );
}
