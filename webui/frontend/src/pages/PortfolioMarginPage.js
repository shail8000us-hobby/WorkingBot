import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import PortfolioMarginPanel from '../components/portfolioMargin/PortfolioMarginPanel';

const PortfolioMarginPage = React.memo(function PortfolioMarginPage() {
    return (
        <div className="grid gap-1">
            <CollapsibleCard
                id="portfolio-margin-panel"
                title="💼 Portfolio Margin"
                subtitle="Monitor & manage portfolio margin — risk, IM/MM, live WebSocket data"
                accent="sky"
                defaultOpen={true}
            >
                <EnhancedErrorBoundary componentName="PortfolioMarginPanel">
                    <PortfolioMarginPanel />
                </EnhancedErrorBoundary>
            </CollapsibleCard>
        </div>
    );
});

export default PortfolioMarginPage;
