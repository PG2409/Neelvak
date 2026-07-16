import { motion } from 'framer-motion'
import { type TraceNode } from '../store'

export default function TraceNodeItem({ node }: { node: TraceNode }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="trace-line-container flex items-start gap-3 py-1.5 text-[13.5px]"
    >
      <div className={`w-6 h-6 rounded flex items-center justify-center ${node.color} shrink-0 z-10 bg-bg-main shadow-sm`}>
        <i className={node.icon}></i>
      </div>
      <span className="text-text-muted mt-0.5" dangerouslySetInnerHTML={{ __html: node.text }}></span>
    </motion.div>
  )
}
