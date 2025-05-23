// skellyclicker-ui/src/layout/BasePanelLayout.tsx
import React from "react"
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {LeftSidePanelContent} from "@/components/layout-components/LeftSidePanelContent";
import BottomPanelContent from "@/components/layout-components/BottomPanelContent";
import {useTheme} from "@mui/material/styles";
import {Box} from "@mui/material";

export const BasePanelLayout = ({children}: { children: React.ReactNode }) => {
    const theme = useTheme();

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            <PanelGroup
                direction="vertical"
                style={{ flex: 1 }}
            >
                {/* Top section (horizontal panels) - 80% height */}
                <Panel defaultSize={80} minSize={20}>
                    <PanelGroup direction="horizontal">
                        <Panel collapsible defaultSize={40} minSize={10} collapsedSize={4}>
                            <LeftSidePanelContent/>
                        </Panel>
                        {/* Horizontal Resize Handle */}
                        <PanelResizeHandle
                            style={{
                                width: "4px",
                                cursor: "col-resize",
                                backgroundColor: theme.palette.primary.light,
                            }}
                        />

                        {/*Main/Central Content Panel*/}
                        <Panel defaultSize={60} minSize={10}>
                            {children}
                        </Panel>
                    </PanelGroup>
                </Panel>

                {/* Vertical Resize Handle */}
                <PanelResizeHandle
                    style={{
                        height: "4px",
                        cursor: "row-resize",
                        backgroundColor: theme.palette.primary.light,
                    }}
                />

                <Panel collapsible defaultSize={20} minSize={10} collapsedSize={4}>
                    <BottomPanelContent/>
                </Panel>
            </PanelGroup>
        </Box>
    )
}
