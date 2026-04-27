// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title HalalCertAnchor
 * @notice Append-only registry of Merkle roots representing batches of Halal
 *         certificates and production batches issued by AMINRA.
 *
 *         Anyone can read; only the configured `owner` (AMINRA's wallet) can
 *         write. Writes are immutable: there is no `update` or `delete`. An
 *         emergency `pause` exists in case of compromise — it stops new
 *         anchors but does NOT modify existing ones.
 *
 *         External verifiers (importers, regulators) compute the Merkle proof
 *         off-chain and call {getAnchor} to retrieve the canonical root.
 */
contract HalalCertAnchor {
    address public immutable owner;
    bool    public paused;

    struct Anchor {
        bytes32 merkleRoot;     // Root of the Merkle tree for this batch
        uint64  timestamp;      // When the anchor was submitted
        uint32  certCount;      // # of cert leaves in the tree
        uint32  batchCount;     // # of production-batch leaves
        string  metadata;       // Optional URI to anchor detail (off-chain)
    }

    /// @notice Sequential anchor ID → Anchor record.
    mapping(uint256 => Anchor) public anchors;

    /// @notice Total number of anchors written. Also = next anchor ID.
    uint256 public anchorCount;

    /// @notice Emitted on every successful anchor write.
    event RootAnchored(
        uint256 indexed anchorId,
        bytes32 indexed merkleRoot,
        uint64  timestamp,
        uint32  certCount,
        uint32  batchCount,
        string  metadata
    );

    /// @notice Emitted when the contract is paused or unpaused.
    event PauseToggled(bool paused);

    error NotOwner();
    error Paused();
    error EmptyRoot();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert Paused();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Submit a new Merkle root anchor. Append-only.
     * @return anchorId  Sequential ID assigned to this anchor.
     */
    function anchorRoot(
        bytes32 _root,
        uint64  _timestamp,
        uint32  _certCount,
        uint32  _batchCount,
        string calldata _metadata
    ) external onlyOwner whenNotPaused returns (uint256 anchorId) {
        if (_root == bytes32(0)) revert EmptyRoot();

        anchorId = anchorCount;
        anchors[anchorId] = Anchor({
            merkleRoot: _root,
            timestamp:  _timestamp,
            certCount:  _certCount,
            batchCount: _batchCount,
            metadata:   _metadata
        });
        unchecked { anchorCount = anchorId + 1; }

        emit RootAnchored(
            anchorId, _root, _timestamp, _certCount, _batchCount, _metadata
        );
    }

    /// @notice Read an anchor by ID. Anyone can call.
    function getAnchor(uint256 _anchorId) external view returns (Anchor memory) {
        return anchors[_anchorId];
    }

    /// @notice Emergency pause / unpause. Only owner.
    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit PauseToggled(_paused);
    }
}
